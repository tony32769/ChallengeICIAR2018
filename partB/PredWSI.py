# -*- coding: utf-8 -*-

import pdb
from optparse import OptionParser
import numpy as np
from skimage import img_as_ubyte
from skimage.io import imsave
from skimage.transform import resize
from os.path import join
from glob import glob
import UsefulFunctions.UsefulOpenSlide as UOS
from openslide import open_slide # http://openslide.org/api/python/
from TissueSegmentation import ROI_binary_mask
from keras.models import load_model

if __name__ == '__main__':

    # Example to fine-tune on 3000 samples from Cifar10
    parser = OptionParser()
    parser.add_option('--fold', dest="fold", type="str")
    parser.add_option('--mean', dest="mean", type="str")
    (options, args) = parser.parse_args()
    mean = np.load(options.mean)

    for num in range(1, 11):
        svs_path = join(options.path, 'A{:02}.svs'.format(num))
        WSI = openslide.OpenSlide(svs_path)

        WEIGHTS = glob("*_fold_{}.h5".format(num))[0]

        last_dim_n = len(WSI.level_dimensions) - 1
        last_dim = WSI.level_dimensions[last_dim_n]
        last_dim_inv = (last_dim[1], last_dim[0])
        whole_img = WSI.read_region((0,0), last_dim_n, last_dim)
        whole_img = np.array(whole_img)[:,:,0:3]


        small_img = resize(whole_img, (500, 500))
        small_img = img_as_ubyte(small_img)
        mask = ROI_binary_mask(small_img, ticket=(80,80,80))
        mask = mask.astype('uint8')
        mask[mask > 0] = 255
        mask_tissue = resize(mask, last_dim_inv, order=0)
        mask_tissue = img_as_ubyte(mask_tissue)
        mask_tissue[mask_tissue > 0] = 255

        class_0 = np.zeros_like(whole_img[:,:,0])
        class_1 = np.zeros_like(whole_img[:,:,0])
        class_2 = np.zeros_like(whole_img[:,:,0])
        class_3 = np.zeros_like(whole_img[:,:,0])
        s_0_x, s_0_y = UOS.get_size(WSI, 224, 224, 0, last_dim_n)

        model = load_model(WEIGHTS)

        for x in range(0, whole_img.shape[0], s_0_x):
            for y in range(0, whole_img.shape[1], s_0_y):
                if mask_tissue[x, y] != 0: 
                    img = WSI.read_region((x-s_0_x/2, y-s_0_y/2), 0, (224, 224))
                    img = img.astype(float) - mean
                    img = np.expand_dims(img, axis=0)
                    res = model.predict(img)
                    class_0[x, y] = res[0]
                    class_1[x, y] = res[1]
                    class_2[x, y] = res[2]
                    class_3[x, y] = res[3]

        save_name = 'class_{}_for_image_{}'
        imsave(save_name.format(0, num), class_0)
        imsave(save_name.format(1, num), class_1)
        imsave(save_name.format(2, num), class_2)
        imsave(save_name.format(3, num), class_3)
