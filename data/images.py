import cv2
import numpy as np
import random


def grayscale(image):
  return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def normalize_(image, mean, std):
  image -= mean
  image /= std


def lighting_(data_rng, image, alphastd, eigval, eigvec):
  alpha = data_rng.normal(scale=alphastd, size=(3,))
  image += np.dot(eigvec, eigval * alpha)


def blend_(alpha, image1, image2):
  image1 *= alpha
  image2 *= (1 - alpha)
  image1 += image2


def saturation_(data_rng, image, gs, gs_mean, var):
  alpha = 1. + data_rng.uniform(low=-var, high=var)
  blend_(alpha, image, gs[:, :, None])


def brightness_(data_rng, image, gs, gs_mean, var):
  alpha = 1. + data_rng.uniform(low=-var, high=var)
  image *= alpha


def contrast_(data_rng, image, gs, gs_mean, var):
  alpha = 1. + data_rng.uniform(low=-var, high=var)
  blend_(alpha, image, gs_mean)


def color_jittering_(data_rng, image):
  functions = [brightness_, contrast_, saturation_]
  random.shuffle(functions)

  gs = grayscale(image)
  gs_mean = gs.mean()
  for f in functions:
    f(data_rng, image, gs, gs_mean, 0.4)


def crop_image(image, center, new_size):
  cty, ctx = center
  height, width = new_size
  im_height, im_width = image.shape[0:2]
  cropped_image = np.zeros((height, width, 3), dtype=image.dtype)

  x0, x1 = max(0, ctx - width // 2), min(ctx + width // 2, im_width)
  y0, y1 = max(0, cty - height // 2), min(cty + height // 2, im_height)

  left, right = ctx - x0, x1 - ctx
  top, bottom = cty - y0, y1 - cty

  cropped_cty, cropped_ctx = height // 2, width // 2
  y_slice = slice(cropped_cty - top, cropped_cty + bottom)
  x_slice = slice(cropped_ctx - left, cropped_ctx + right)
  cropped_image[y_slice, x_slice, :] = image[y0:y1, x0:x1, :]

  border = np.array([
    cropped_cty - top,
    cropped_cty + bottom,
    cropped_ctx - left,
    cropped_ctx + right
  ], dtype=np.float32)

  offset = np.array([
    cty - height // 2,
    ctx - width // 2
  ])

  return cropped_image, border, offset


def _get_border(border, size):
  i = 1
  while size - border // i <= border // i:
    i *= 2
  return border // i


def random_crop(image, detections, random_scales, new_size, padding):
  new_height, new_width = new_size['h'], new_size['w']
  image_height, image_width = image.shape[0:2]

  scale = np.random.choice(random_scales)
  new_height = int(new_height * scale)
  new_width = int(new_width * scale)

  cropped_image = np.zeros((new_height, new_width, 3), dtype=image.dtype)

  w_border = _get_border(padding, image_width)
  h_border = _get_border(padding, image_height)

  # choose a random center point
  center_x = np.random.randint(low=w_border, high=image_width - w_border)
  center_y = np.random.randint(low=h_border, high=image_height - h_border)

  # get the four coordinates according to this center point
  left, right = max(center_x - new_width // 2, 0), min(center_x + new_width // 2, image_width)
  bottom, top = max(center_y - new_height // 2, 0), min(center_y + new_height // 2, image_height)

  left_w, right_w = center_x - left, right - center_x
  top_h, bottom_h = center_y - bottom, top - center_y

  # crop image
  cropped_center_x, cropped_center_y = new_width // 2, new_height // 2
  x_slice = slice(cropped_center_x - left_w, cropped_center_x + right_w)
  y_slice = slice(cropped_center_y - top_h, cropped_center_y + bottom_h)
  cropped_image[y_slice, x_slice, :] = image[bottom:top, left:right, :]

  # crop detections
  cropped_detections = detections.copy()
  cropped_detections[:, 0::2] -= left
  cropped_detections[:, 1::2] -= bottom
  cropped_detections[:, 0::2] += cropped_center_x - left_w
  cropped_detections[:, 1::2] += cropped_center_y - top_h

  return cropped_image, cropped_detections


def random_crop_v2(image, detections, random_scales, new_size):
  new_height, new_width = new_size['h'], new_size['w']
  image_height, image_width = image.shape[0:2]

  scale = np.random.choice(random_scales)
  scaled_height = int(image_height * scale)
  scaled_width = int(image_width * scale)

  new_image = np.zeros((new_height, new_width, 3), dtype=image.dtype)

  scaled_image = cv2.resize(image, (scaled_width, scaled_height))
  new_detections = detections * scale

  offset_x = int(np.random.uniform(0, 1) * np.abs(scaled_width - new_width))
  offset_y = int(np.random.uniform(0, 1) * np.abs(scaled_height - new_height))

  # crop image and bboxes
  if scaled_width > new_width and scaled_height > new_height:
    new_image[:, :, :] = \
      scaled_image[offset_y:offset_y + new_height, offset_x:offset_x + new_width, :]
    new_detections[:, 0::2] -= offset_x
    new_detections[:, 1::2] -= offset_y
  elif scaled_width > new_width and scaled_height <= new_height:
    new_image[offset_y:offset_y + scaled_height, :, :] = \
      scaled_image[:, offset_x:offset_x + new_width, :]
    new_detections[:, 0::2] -= offset_x
    new_detections[:, 1::2] += offset_y
  elif scaled_width <= new_width and scaled_height > new_height:
    new_image[:, offset_x:offset_x + scaled_width, :] = \
      scaled_image[offset_y:offset_y + new_height, :, :]
    new_detections[:, 0::2] += offset_x
    new_detections[:, 1::2] -= offset_y
  else:
    new_image[offset_y:offset_y + scaled_height, offset_x:offset_x + scaled_width, :] = \
      scaled_image
    new_detections[:, 0::2] += offset_x
    new_detections[:, 1::2] += offset_y

  return new_image, new_detections, 0, 0, 0, 0


def center_crop_v2(image, detections, new_size):
  new_height, new_width = new_size['h'], new_size['w']
  image_height, image_width = image.shape[0:2]

  scale = np.minimum(new_height / image_height, new_width / image_width)
  scaled_height = int(image_height * scale)
  scaled_width = int(image_width * scale)

  new_image = np.zeros((new_height, new_width, 3), dtype=image.dtype)

  scaled_image = cv2.resize(image, (scaled_width, scaled_height))
  new_detections = detections * scale

  offset_x = int(0.5 * np.abs(scaled_width - new_width))
  offset_y = int(0.5 * np.abs(scaled_height - new_height))

  # crop image and bboxes
  new_image[offset_y:offset_y + scaled_height, offset_x:offset_x + scaled_width, :] = scaled_image
  new_detections[:, 0::2] += offset_x
  new_detections[:, 1::2] += offset_y

  return new_image, new_detections, offset_x, offset_y, scaled_width, scaled_height


if __name__ == '__main__':
  import cv2
  import torch

  img = cv2.imread('E:\\coco_debug\\coco\\train2017\\000000102912.jpg')
  bbox = np.array([[282, 146, 238, 270],
                   [0, 85, 332, 389]])
  bbox[:, 2:] += bbox[:, :2]
  img, bbox = random_crop(img, detections=bbox, random_scales=np.arange(0.6, 1.4, 0.1),
                          new_size={'w': 512, 'h': 512}, padding=128)

  torch.save([img, bbox], 'crop.t7')
