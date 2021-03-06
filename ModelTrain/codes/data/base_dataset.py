import os
import random
import numpy as np
import torch.utils.data as data
import torchvision.transforms as transforms

try:
    from PIL import Image
except:
    pass

from dataops.common import get_image_paths, read_img


class BaseDataset(data.Dataset):
    """This class is an base Dataset class for datasets.
    To create a subclass, you need to implement the following four functions:
    -- <__init__>: initialize the class, first call BaseDataset.__init__(self, opt).
    -- <__len__>: return the size of dataset.
    -- <__getitem__>: get a data point.
    -- <name>: returns the dataset name if defined, else returns BaseDataset
    """

    def __init__(self, opt, keys_ds=['A','B']):
        """Initialize the class; save the options in the class
        Parameters:
            opt (Options dictionary): stores all the experiment flags
            keys_ds (list): the paired 'dataroot_' properties names expected in the Dataset. ie:
                dataroot_A-dataroot_B or dataroot_LR-dataroot_HR. Will check for correct names in
                the opt dictionary and modify if needed. For single dataroot cases, will use the
                first element.
        """

        opt = check_data_keys(opt, keys_ds=keys_ds)
        self.opt = opt
        self.keys_ds = keys_ds

    def __len__(self):
        """Return the total number of images in the dataset."""
        return 0

    def __getitem__(self, index):
        """Return a data point and its metadata information.
        Parameters:
            index - - a random integer for data indexing
        Returns:
            a dictionary of data with their names. It ususally contains the data itself and its metadata information.
        """
        pass

    def name(self):
        return self.opt.get('name', 'BaseDataset')





def process_img_paths(images_paths, data_type='img'):
    # process images_paths
    paths_list = []
    for path in images_paths:
        paths = get_image_paths(data_type, path)
        for imgs in paths:
            paths_list.append(imgs)
    paths_list = sorted(paths_list)
    return paths_list


def read_subset(dataroot, subset_file):
    with open(subset_file) as f:
        paths = sorted([os.path.join(dataroot, line.rstrip('\n')) for line in f])
    return paths


def format_paths(dataroot):
    """
    Check if dataroot_HR is a list of directories or a single directory. 
    Note: lmdb will not currently work with a list
    """
    # if receiving a single path in str format, convert to list
    if type(dataroot) is str:
        dataroot = os.path.join(dataroot)
        dataroot = [dataroot]
    
    assert isinstance(dataroot, list)
    return dataroot


def paired_dataset_validation(A_images_paths, B_images_paths, data_type='img', max_dataset_size=float("inf")):

    if isinstance(A_images_paths, str) and isinstance(B_images_paths, str):
        A_images_paths = [A_images_paths]
        B_images_paths = [B_images_paths]

    paths_A = []
    paths_B = []
    for paths in zip(A_images_paths, B_images_paths):
        A_paths = get_image_paths(data_type, paths[0], max_dataset_size)  # get image paths
        B_paths = get_image_paths(data_type, paths[1], max_dataset_size)  # get image paths
        for imgs in zip(A_paths, B_paths):
            _, A_filename = os.path.split(imgs[0])
            _, B_filename = os.path.split(imgs[1])
            assert A_filename == B_filename, 'Wrong pair of images {} and {}'.format(A_filename, B_filename)
            paths_A.append(imgs[0])
            paths_B.append(imgs[1])
    return paths_A, paths_B


def check_data_keys(opt, keys_ds=['LR', 'HR']):
    keys_A = ['LR', 'A', 'lq']
    keys_B = ['HR', 'B', 'gt']
    
    root_A = 'dataroot_' + keys_ds[0]
    root_B = 'dataroot_' + keys_ds[1]
    for pair_keys in zip(keys_A, keys_B):
        A_el = 'dataroot_' + pair_keys[0]
        B_el = 'dataroot_' + pair_keys[1]
        if opt.get(B_el, None) and B_el != root_B:
            opt[root_B] = opt[B_el]
            opt.pop(B_el)
        if opt.get(A_el, None) and A_el != root_A:
            opt[root_A] = opt[A_el]
            opt.pop(A_el)
    
    return opt



def read_dataroots(opt, keys_ds=['LR','HR']):
    """ Read the dataroots from the options dictionary
    Parameters:
        opt (Options dictionary): stores all the experiment flags
        keys_ds (list): the paired 'dataroot_' properties names expected in the Dataset.
            Note that `LR` dataset corresponds to `A` or `lq` domain, while `HR` 
            corresponds to `B` or `gt`
    """
    paths_A, paths_B = None, None
    root_A = 'dataroot_' + keys_ds[0]
    root_B = 'dataroot_' + keys_ds[1]

    # read image list from subset list txt
    if opt['subset_file'] is not None and opt['phase'] == 'train':
        paths_B = read_subset(opt[root_B], opt['subset_file'])
        if opt[root_A] is not None and opt.get('subset_file_'+keys_ds[0], None):
            paths_A = read_subset(opt[root_A], opt['subset_file'])
        else:
            print('Using subset will generate {}s on-the-fly.').format(keys_ds[0])
    else:  # read image list from lmdb or image files
        A_images_paths = format_paths(opt[root_A])
        B_images_paths = format_paths(opt[root_B])
        
        # special case when dealing with duplicate B_images_paths or A_images_paths
        # lmdb not be supported with this option
        if len(B_images_paths) != len(set(B_images_paths)) or \
            len(A_images_paths) != len(set(A_images_paths)):

            # only resolve when the two path lists coincide in the number of elements, 
            # they have to be ordered specifically as they will be used in the options file
            assert len(B_images_paths) == len(A_images_paths), \
                'Error: When using duplicate paths, {} and {} must contain the same number of elements.'.format(
                    root_B, root_A)

            paths_A, paths_B = paired_dataset_validation(A_images_paths, B_images_paths, 
                                        opt['data_type'], opt.get('max_dataset_size', float("inf")))
        else: # for cases with extra HR directories for OTF images or original single directories
            paths_A = process_img_paths(A_images_paths, opt['data_type'])
            paths_B = process_img_paths(B_images_paths, opt['data_type'])

    return paths_A, paths_B


def validate_paths(paths_A, paths_B, strict=True, keys_ds=['LR','HR']):
    """ Validate the constructed images path lists are consistent. 
    Can allow using B/HR and A/LR folders with different amount of images
    Parameters:
        paths_A (str): the path to domain A
        paths_B (str): the path to domain B
        keys_ds (list): the paired 'dataroot_' properties names expected in the Dataset.
        strict (bool): If strict = True, will make sure both lists only contains images
            if properly paired in the other dataset, otherwise will fill missing images 
            paths in LR/A with 'None' to be taken care of later (ie. with on-the-fly 
            generation)
    Examples of OTF usage:
    - If an LR image pair is not found, downscale HR on the fly, else, use the LR
    - If all LR are provided and 'lr_downscale' is enabled, randomize use of provided 
        LR and OTF LR for augmentation
    """
    
    if not strict:
        assert len(paths_B) >= len(paths_A), \
            '{} dataset contains less images than {} dataset  - {}, {}.'.format(\
            keys_ds[1], keys_ds[0], len(paths_B), len(paths_A))
        if len(paths_A) < len(paths_B):
            print('{} contains less images than {} dataset  - {}, {}. Will generate missing images on the fly.'.format(
                keys_ds[0], keys_ds[1], len(paths_A), len(paths_B)))

    i=0
    tmp_A = []
    tmp_B = []
    for idx in range(0, len(paths_B)):
        B_head, B_tail = os.path.split(paths_B[idx])
        if i < len(paths_A):
            A_head, A_tail = os.path.split(paths_A[i])
            
            if A_tail == B_tail:
                A_img_path = os.path.join(A_head, A_tail)
                tmp_A.append(A_img_path)
                i+=1
                if strict:
                    B_img_path = os.path.join(B_head, B_tail)
                    tmp_B.append(B_img_path)
            else:
                if not strict:
                    A_img_path = None
                    tmp_A.append(A_img_path)
        else: #if the last image is missing
            if not strict:
                A_img_path = None
                tmp_A.append(A_img_path)
    paths_A = tmp_A
    paths_B = tmp_B if strict else paths_B

    assert len(paths_A) == len(paths_B)
    return paths_A, paths_B


def get_dataroots_paths(opt, strict=False, keys_ds=['LR', 'HR']):
    paths_A, paths_B = read_dataroots(opt, keys_ds=keys_ds)
    assert paths_B, 'Error: {} path is empty.'.format(keys_ds[1])
    if strict:
        assert paths_A, 'Error: {} path is empty.'.format(keys_ds[0])

    if paths_A and paths_B:
        paths_A, paths_B = validate_paths(paths_A, paths_B, strict=strict, keys_ds=keys_ds)
    return paths_A, paths_B
