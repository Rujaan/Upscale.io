import os.path
import random
import numpy as np
import cv2
import torch
import dataops.common as util

import dataops.augmentations as augmentations
from dataops.debug import tmp_vis, describe_numpy, describe_tensor
from data.base_dataset import BaseDataset, get_dataroots_paths


class LRHRDataset(BaseDataset):
    '''
    Read LR and HR image pairs.
    If only HR image is provided, generate LR image on-the-fly.
    The pair is ensured by 'sorted' function, so please check the name convention.
    '''

    def __init__(self, opt):
        super(LRHRDataset, self).__init__(opt, keys_ds=['LR','HR'])
        # self.opt = opt
        # self.paths_LR, self.paths_HR = None, None
        self.LR_env, self.HR_env = None, None  # environment for lmdb
        self.output_sample_imgs = None

        # get images paths (and optional environments for lmdb) from dataroots
        self.paths_LR, self.paths_HR = get_dataroots_paths(opt, strict=False, keys_ds=self.keys_ds)
        
        if self.opt.get('data_type') == 'lmdb':
            self.LR_env = util._init_lmdb(opt.get('dataroot_'+self.keys_ds[0]))
            self.HR_env = util._init_lmdb(opt.get('dataroot_'+self.keys_ds[1]))

        #self.random_scale_list = [1]

    def __getitem__(self, index):
        HR_path, LR_path = None, None
        data_type = self.opt.get('data_type', 'img')
        scale = self.opt['scale']
        HR_size = self.opt['HR_size']
        if HR_size:
            LR_size = HR_size // scale
        
        # Default case: tensor will result in the [0,1] range
        # Alternative: tensor will be z-normalized to the [-1,1] range
        znorm  = self.opt.get('znorm', False)
        
        ######## Read the images ########
        #TODO: check cases where default of 3 channels will be troublesome
        image_channels  = self.opt.get('image_channels', 3)
        
        # Check if LR Path is provided
        if self.paths_LR:
            #If LR is provided, check if 'rand_flip_LR_HR' is enabled
            if self.opt.get('rand_flip_LR_HR', None) and self.opt['phase'] == 'train':
                LRHRchance = random.uniform(0, 1)
                flip_chance  = self.opt.get('flip_chance', 0.05)
                #print("Random Flip Enabled")
            # Normal case, no flipping:
            else:
                LRHRchance = 0.
                flip_chance = 0.
                #print("No Random Flip")

            # get HR and LR images
            # If enabled, random chance that LR and HR images are flipped
            # Normal case, no flipping
            # If img_LR (LR_path) doesn't exist, use img_HR (HR_path)
            if LRHRchance < (1- flip_chance):
                HR_path = self.paths_HR[index]
                LR_path = self.paths_LR[index]
                if LR_path is None:
                    LR_path = HR_path
                #print("HR kept")
            # Flipped case:
            # If img_HR (LR_path) doesn't exist, use img_HR (LR_path)
            else:
                HR_path = self.paths_LR[index]
                LR_path = self.paths_HR[index]
                if HR_path is None:
                    HR_path = LR_path
                #print("HR flipped")

            # Read the LR and HR images from the provided paths
            img_LR = util.read_img(env=data_type, path=LR_path, lmdb_env=self.LR_env, out_nc=image_channels)
            img_HR = util.read_img(env=data_type, path=HR_path, lmdb_env=self.HR_env, out_nc=image_channels)
            
            # Even if LR dataset is provided, force to generate aug_downscale % of downscales OTF from HR
            # The code will later make sure img_LR has the correct size
            if self.opt.get('aug_downscale', None):
                if np.random.rand() < self.opt['aug_downscale']:
                    img_LR = img_HR
            
        # If LR is not provided, use HR and modify on the fly
        else:
            HR_path = self.paths_HR[index]
            img_HR = util.read_img(env=data_type, path=HR_path, lmdb_env=self.HR_env, out_nc=image_channels)
            img_LR = img_HR
            LR_path = HR_path
        
        ######## Modify the images ########
        
        # HR modcrop in the validation / test phase
        if self.opt['phase'] != 'train':
            img_HR = util.modcrop(img_HR, scale)
        
        # change color space if necessary
        # Note: Changing the LR colorspace here could make it so some colors are introduced when 
        #  doing the augmentations later (ie: with Gaussian or Speckle noise), may be good if the
        #  model can learn to remove color noise in grayscale images, otherwise move to before
        #  converting to tensors
        # self.opt['color'] For both LR and HR as in the the original code, kept for compatibility
        # self.opt['color_HR'] and self.opt['color_LR'] for independent control
        if self.opt.get('color', None): # Change both
            img_HR = util.channel_convert(img_HR.shape[2], self.opt['color'], [img_HR])[0]
            img_LR = util.channel_convert(img_LR.shape[2], self.opt['color'], [img_LR])[0]
        if self.opt.get('color_HR', None): # Only change HR
            img_HR = util.channel_convert(img_HR.shape[2], self.opt['color_HR'], [img_HR])[0] 
        if self.opt.get('color_LR', None): # Only change LR
            img_LR = util.channel_convert(img_LR.shape[2], self.opt['color_LR'], [img_LR])[0]

        ######## Augmentations ########
        
        #Augmentations during training
        if self.opt['phase'] == 'train':
            
            # Note: this is NOT recommended, HR should not be exposed to degradation, as it will 
            # degrade the model's results, only added because it exist as an option in downstream forks
            # HR downscale
            if self.opt.get('hr_downscale', None): 
                ds_algo  = self.opt.get('hr_downscale_types', 777)
                hr_downscale_amt  = self.opt.get('hr_downscale_amt', 2)
                if isinstance(hr_downscale_amt, list):
                    hr_downscale_amt = random.choice(hr_downscale_amt)
                # will ignore if 1 or if result is smaller than hr size
                if hr_downscale_amt > 1 and img_HR.shape[0]//hr_downscale_amt >= HR_size and img_HR.shape[1]//hr_downscale_amt >= HR_size:
                    img_HR, hr_scale_interpol_algo = augmentations.scale_img(img_HR, hr_downscale_amt, algo=ds_algo)
                    # Downscales LR to match new size of HR if scale does not match after
                    if img_LR is not None and (img_HR.shape[0] // scale != img_LR.shape[0] or img_HR.shape[1] // scale != img_LR.shape[1]):
                        img_LR, lr_scale_interpol_algo = augmentations.scale_img(img_LR, hr_downscale_amt, algo=hr_scale_interpol_algo)

            # Validate there's an img_LR, if not, use img_HR
            if img_LR is None:
                img_LR = img_HR
                print("Image LR: ", LR_path, ("was not loaded correctly, using HR pair to downscale on the fly."))
            
            # Check that HR and LR have the same dimensions ratio, else, generate new LR from HR
            if img_HR.shape[0]//img_LR.shape[0] != img_HR.shape[1]//img_LR.shape[1]:
                #TODO: disabled to test cx loss 
                #print("Warning: img_LR dimensions ratio does not match img_HR dimensions ratio for: ", HR_path)
                #TODO: temporary change to test contextual loss with unaligned LR-HR pairs, forcing them to have the correct scale
                img_HR, _ = augmentations.resize_img(np.copy(img_HR), newdim=(img_LR.shape[1]*scale,img_LR.shape[0]*scale), algo=cv2.INTER_LINEAR)
                #img_LR = img_HR
            
            # Random Crop (reduce computing cost and adjust images to correct size first)
            if img_HR.shape[0] > HR_size or img_HR.shape[1] > HR_size:
                #Here the scale should be in respect to the images, not to the training scale (in case they are being scaled on the fly)
                scaleor = img_HR.shape[0]//img_LR.shape[0]
                img_HR, img_LR = augmentations.random_crop_pairs(img_HR, img_LR, HR_size, scaleor)
            
            # Or if the HR images are too small, Resize to the HR_size size and fit LR pair to LR_size too
            if img_HR.shape[0] < HR_size or img_HR.shape[1] < HR_size:
                #TODO: temp disabled to test
                #print("Warning: Image: ", HR_path, " size does not match HR size: (", HR_size,"). The image size is: ", img_HR.shape)
                # rescale HR image to the HR_size 
                img_HR, _ = augmentations.resize_img(np.copy(img_HR), newdim=(HR_size,HR_size), algo=cv2.INTER_LINEAR)
                # rescale LR image to the LR_size (The original code discarded the img_LR and generated a new one on the fly from img_HR)
                img_LR, _ = augmentations.resize_img(np.copy(img_LR), newdim=(LR_size,LR_size), algo=cv2.INTER_LINEAR)
            
            # Randomly scale LR from HR during training if :
            # - LR dataset is not provided
            # - LR dataset is not in the correct scale
            # - Also to check if LR is not at the correct scale already (if img_LR was changed to img_HR)
            if img_LR.shape[0] != LR_size or img_LR.shape[1] != LR_size:
                ds_algo = 777 # default to matlab-like bicubic downscale
                if self.opt.get('lr_downscale', None): # if manually set and scale algorithms are provided, then:
                    ds_algo  = self.opt.get('lr_downscale_types', 777)
                else: # else, if for some reason img_LR is too large, default to matlab-like bicubic downscale
                    #if not self.opt['aug_downscale']: #only print the warning if not being forced to use HR images instead of LR dataset (which is a known case)
                    print("LR image is too large, auto generating new LR for: ", LR_path)
                img_LR, scale_interpol_algo = augmentations.scale_img(img_LR, scale, algo=ds_algo)
            #"""
            
            # Rotations. 'use_flip' = 180 or 270 degrees (mirror), 'use_rot' = 90 degrees, 'HR_rrot' = random rotations +-45 degrees
            if (self.opt['use_flip'] or self.opt['use_rot']) and self.opt.get('hr_rrot', None):
                if np.random.rand() > 0.5:
                    img_LR, img_HR = util.augment([img_LR, img_HR], self.opt['use_flip'], \
                        self.opt['use_rot'])
                else:
                    if np.random.rand() > 0.5: # randomize the random rotations, so half the images are the original
                        img_HR, img_LR = augmentations.random_rotate_pairs(img_HR, img_LR, HR_size, scale)
            elif (self.opt['use_flip'] or self.opt['use_rot']) and not self.opt.get('hr_rrot', None):
                # augmentation - flip, rotate
                img_LR, img_HR = util.augment([img_LR, img_HR], self.opt['use_flip'], \
                    self.opt['use_rot'])
            elif self.opt.get('hr_rrot', None):
                if np.random.rand() > 0.5: # randomize the random rotations, so half the images are the original
                    img_HR, img_LR = augmentations.random_rotate_pairs(img_HR, img_LR, HR_size, scale)
            
            
            # Final sizes checks
            # if the resulting HR image size so far is too large or too small, resize HR to the correct size and downscale to generate a new LR on the fly
            # if the resulting LR so far does not have the correct dimensions, also generate a new HR-LR image pair on the fly
            if img_HR.shape[0] != HR_size or img_HR.shape[1] != HR_size or img_LR.shape[0] != LR_size or img_LR.shape[1] != LR_size:

                #if img_HR.shape[0] != HR_size or img_HR.shape[1] != HR_size:
                    #TODO: temp disabled to test
                    #print("Image: ", HR_path, " size does not match HR size: (", HR_size,"). The image size is: ", img_HR.shape)
                #if img_LR.shape[0] != LR_size or img_LR.shape[0] != LR_size:
                    #TODO: temp disabled to test
                    #print("Image: ", LR_path, " size does not match LR size: (", HR_size//scale,"). The image size is: ", img_LR.shape)

                # rescale HR image to the HR_size (should not be needed in LR case, but something went wrong before, just for sanity)
                img_HR, _ = augmentations.resize_img(np.copy(img_HR), newdim=(HR_size,HR_size), algo=cv2.INTER_LINEAR)
                # if manually provided and scale algorithms are provided, then use it, else use matlab imresize to generate LR pair
                ds_algo  = self.opt.get('lr_downscale_types', 777) 
                img_LR, _ = augmentations.scale_img(img_HR, scale, algo=ds_algo)
            
            
            # Below are the On The Fly augmentations

            # Apply "auto levels" to images
            rand_levels = (1 - self.opt.get('rand_auto_levels', 0)) # Randomize for augmentation
            if self.opt.get('auto_levels', None) and np.random.rand() > rand_levels:
                if self.opt['auto_levels'] == 'HR':
                    #img_HR = augmentations.simplest_cb(img_HR, znorm=znorm) #TODO: now images are processed in the [0,255] range
                    img_HR = augmentations.simplest_cb(img_HR)
                elif self.opt['auto_levels'] == 'LR':
                    #img_LR = augmentations.simplest_cb(img_LR, znorm=znorm) #TODO: now images are processed in the [0,255] range
                    img_LR = augmentations.simplest_cb(img_LR)
                elif self.opt['auto_levels'] == True or self.opt['auto_levels'] == 'Both':
                    #img_HR = augmentations.simplest_cb(img_HR, znorm=znorm) #TODO: now images are processed in the [0,255] range
                    img_HR = augmentations.simplest_cb(img_HR)
                    #img_LR = augmentations.simplest_cb(img_LR, znorm=znorm) #TODO: now images are processed in the [0,255] range
                    img_LR = augmentations.simplest_cb(img_LR)
            
            # Apply unsharpening mask to LR images
            rand_unsharp = (1 - self.opt.get('lr_rand_unsharp', 0)) # Randomize for augmentation
            if self.opt.get('lr_unsharp_mask', None) and np.random.rand() > rand_unsharp:
                #img_LR = augmentations.unsharp_mask(img_LR, znorm=znorm) #TODO: now images are processed in the [0,255] range
                img_LR = augmentations.unsharp_mask(img_LR)

            # Apply unsharpening mask to HR images
            rand_unsharp = (1 - self.opt.get('hr_rand_unsharp', 0)) # Randomize for augmentation
            if self.opt.get('hr_unsharp_mask', None) and np.random.rand() > rand_unsharp:
                #img_HR = augmentations.unsharp_mask(img_HR, znorm=znorm) #TODO: now images are processed in the [0,255] range
                img_HR = augmentations.unsharp_mask(img_HR)


            # Add noise to HR if enabled AND noise types are provided (for noise2noise and similar)
            if self.opt.get('hr_noise', None):
                if self.opt['hr_noise_types']:
                    img_HR, hr_noise_algo = augmentations.noise_img(img_HR, noise_types=self.opt['hr_noise_types'])
                else:
                    print("Noise types 'hr_noise_types' not defined. Skipping OTF noise for HR.")
            
            # Create color fringes
            # Caution: Can easily destabilize a model
            # Only applied to a small % of the images. Around 20% and 50% appears to be stable.
            if self.opt.get('lr_fringes', None):
                lr_fringes_chance = self.opt['lr_fringes_chance'] if self.opt['lr_fringes_chance'] else 0.4
                if np.random.rand() > (1.- lr_fringes_chance):
                    img_LR = augmentations.translate_chan(img_LR)
            
            #"""
            #v LR blur AND blur types are provided, else will skip
            if self.opt.get('lr_blur', None):
                if self.opt.get('lr_blur_types', None):
                    img_LR, blur_algo, blur_kernel_size = augmentations.blur_img(img_LR, blur_algos=self.opt['lr_blur_types'])
                else:
                    print("Blur types 'lr_blur_types' not defined. Skipping OTF blur.")
            #"""
                
            #"""
            #v LR primary noise: Add noise to LR if enabled AND noise types are provided, else will skip
            if self.opt.get('lr_noise', None):
                if self.opt.get('lr_noise_types', None):
                    img_LR, noise_algo = augmentations.noise_img(img_LR, noise_types=self.opt['lr_noise_types'])
                else:
                    print("Noise types 'lr_noise_types' not defined. Skipping OTF noise.")
            #v LR secondary noise: Add additional noise to LR if enabled AND noise types are provided, else will skip
            if self.opt.get('lr_noise2', None):
                if self.opt.get('lr_noise_types2', None):
                    img_LR, noise_algo2 = augmentations.noise_img(img_LR, noise_types=self.opt['lr_noise_types2'])
                else:
                    print("Noise types 'lr_noise_types2' not defined. Skipping OTF secondary noise.")
            #"""
                
            #"""
            #v LR cutout / LR random erasing (for inpainting/classification tests)
            if self.opt.get('lr_cutout', None) and (self.opt.get('lr_erasing', None)  != True):
                img_LR = augmentations.cutout(img_LR, img_LR.shape[0] // 2)
            elif self.opt.get('lr_erasing', None) and (self.opt.get('lr_cutout', None)  != True):
                img_LR = augmentations.random_erasing(img_LR)
            elif self.opt.get('lr_cutout', None) and self.opt.get('lr_erasing', None):
                if np.random.rand() > 0.5: #only do cutout or erasing, not both at the same time
                    img_LR = augmentations.cutout(img_LR, img_LR.shape[0] // 2, p=0.5)
                else:
                    img_LR = augmentations.random_erasing(img_LR, p=0.5, modes=[3])                
            #"""
            
        
        # For testing and validation
        if self.opt['phase'] != 'train':
            # Randomly downscale LR if enabled 
            if self.opt['lr_downscale']:
                if self.opt['lr_downscale_types']:
                    img_LR, scale_interpol_algo = augmentations.scale_img(img_LR, scale, algo=self.opt['lr_downscale_types'])
                else: # Default to matlab-like bicubic downscale
                    img_LR, scale_interpol_algo = augmentations.scale_img(img_LR, scale, algo=777)
        
        # Alternative position for changing the colorspace of LR. 
        # if self.opt['color_LR']: # Only change LR
            # img_LR = util.channel_convert(img_LR.shape[2], self.opt['color'], [img_LR])[0]
            
        # Debug #TODO: use the debugging functions to visualize or save images instead
        # Save img_LR and img_HR images to a directory to visualize what is the result of the on the fly augmentations
        # DO NOT LEAVE ON DURING REAL TRAINING
        # self.output_sample_imgs = True
        if self.opt['phase'] == 'train':
            if self.output_sample_imgs:
                import os
                # LR_dir, im_name = os.path.split(LR_path)
                HR_dir, im_name = os.path.split(HR_path)
                #baseHRdir, _ = os.path.split(HR_dir)
                #debugpath = os.path.join(baseHRdir, os.sep, 'sampleOTFimgs')
                
                # debugpath = os.path.join(os.path.split(LR_dir)[0], 'sampleOTFimgs')
                debugpath = os.path.join('D:/tmp_test', 'sampleOTFimgs')
                #print(debugpath)
                if not os.path.exists(debugpath):
                    os.makedirs(debugpath)
                
                import uuid
                hex = uuid.uuid4().hex
                cv2.imwrite(debugpath+"\\"+im_name+hex+'_LR.png',img_LR) #random name to save
                cv2.imwrite(debugpath+"\\"+im_name+hex+'_HR.png',img_HR) #random name to save
                # cv2.imwrite(debugpath+"\\"+im_name+hex+'_HR1.png',img_HRn1) #random name to save
            
        ######## Convert images to PyTorch Tensors ########
        
        """ # for debugging
        if (img_HR.min() < -1):
            describe_numpy(img_HR, all=True)
            print(HR_path)
        if (img_HR.max() > 1):
            describe_numpy(img_HR, all=True)
            print(HR_path)
        if (img_LR.min() < -1):
            describe_numpy(img_LR, all=True)
            print(LR_path)
        if (img_LR.max() > 1):
            describe_numpy(img_LR, all=True)
            print(LR_path)
        #"""
        
        # check for grayscale images #TODO: should not be needed anymore
        if len(img_HR.shape) < 3:
            img_HR = img_HR[..., np.newaxis]
        if len(img_LR.shape) < 3:
            img_LR = img_LR[..., np.newaxis]
        
        img_HR = util.np2tensor(img_HR, normalize=znorm, add_batch=False)
        img_LR = util.np2tensor(img_LR, normalize=znorm, add_batch=False)
        
        if LR_path is None:
            LR_path = HR_path
        return {'LR': img_LR, 'HR': img_HR, 'LR_path': LR_path, 'HR_path': HR_path} 

    def __len__(self):
        return len(self.paths_HR)
        
