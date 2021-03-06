"""Initial migration.

Revision ID: d1ed6791484c
Revises: 7a223a60e95b
Create Date: 2021-05-02 09:35:20.709925

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd1ed6791484c'
down_revision = '7a223a60e95b'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('contact_us',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('email', sa.String(length=250), nullable=False),
    sa.Column('subject', sa.String(length=300), nullable=False),
    sa.Column('message', sa.String(length=500), nullable=False),
    sa.Column('time', sa.String(length=80), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('contact_us')
    # ### end Alembic commands ###
