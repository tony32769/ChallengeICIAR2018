# -*- coding: utf-8 -*-
import openslide
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
    parser.add_option('--k', dest="k", type="int")
    parser.add_option('--mean', dest="mean", type="str")
    (options, args) = parser.parse_args()

    mean = np.load(options.mean)
    num = options.k
    svs_path = join(options.fold, 'A{:02}.svs'.format(num))
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

    class_0 = np.zeros_like(whole_img[:,:,0], dtype=float)
    class_1 = np.zeros_like(whole_img[:,:,0], dtype=float)
    class_2 = np.zeros_like(whole_img[:,:,0], dtype=float)
    class_3 = np.zeros_like(whole_img[:,:,0], dtype=float)
    s_0_x, s_0_y = UOS.get_size(WSI, 2 * 448, 2 * 448, 0, last_dim_n)
    model = load_model(WEIGHTS)

    for x in range(0, whole_img.shape[0], s_0_x):
        for y in range(0, whole_img.shape[1], s_0_y):
            if mask_tissue[x, y] != 0:
                x_0, y_0 = UOS.get_X_Y(WSI, y, x, last_dim_n)
                img = resize(np.array(WSI.read_region((x_0, y_0), 0, (448 * 2, 448 * 2)))[:,:,0:3], (224, 224))
                img = img_as_ubyte(img).astype(float) - mean
                img = np.expand_dims(img, axis=0)
                res = model.predict(img)
                class_0[x:(x + s_0_x), y:(y + s_0_y)] = res[0][0]
                class_1[x:(x + s_0_x), y:(y + s_0_y)] = res[0][1]
                class_2[x:(x + s_0_x), y:(y + s_0_y)] = res[0][2]
                class_3[x:(x + s_0_x), y:(y + s_0_y)] = res[0][3]
    save_name = WEIGHTS.replace("fold_{}.h5".format(num), 'image_{}_class_{}.png')
    imsave(save_name.format(num, 0), img_as_ubyte(class_0))
    imsave(save_name.format(num, 1), img_as_ubyte(class_1))
    imsave(save_name.format(num, 2), img_as_ubyte(class_2))
    imsave(save_name.format(num, 3), img_as_ubyte(class_3))
