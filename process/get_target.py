import time
import cv2
import numpy as np
import tensorflow as tf
from process.yolov3_tf2.models import YoloV3
from process.yolov3_tf2.dataset import transform_images, load_tfrecord_dataset
from process.yolov3_tf2.utils import draw_outputs
import os

from process.init import yolo, class_names
size = 416

# ./static/videos/output.avi
def getTarget(video, caseID):

    output = "./static/videos/{}/output.avi".format(caseID)

    vid = cv2.VideoCapture(video)

    width = int(vid.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(vid.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(vid.get(cv2.CAP_PROP_FPS))
    codec = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter(output, codec, fps, (width, height))

    fps = 0.0
    count = 0

    while True:
        _, img = vid.read()

        if img is None:
            print("Empty Frame")
            count+=1
            if count < 3:
                continue
            else: 
                break

        img_in = cv2.cvtColor(img, cv2.COLOR_BGR2RGB) 
        img_in = tf.expand_dims(img_in, 0)
        img_in = transform_images(img_in, size)

        t1 = time.time()
        boxes, scores, classes, nums = yolo.predict(img_in)
        fps  = ( fps + (1./(time.time()-t1)) ) / 2

        print("FPS: " + fps)

        img = draw_outputs(img, (boxes, scores, classes, nums), class_names)

        out.write(img)

    link = "http://35.225.41.24/videos/{}/output.avi".format(caseID)
    return link