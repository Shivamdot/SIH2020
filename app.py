import os
import cv2
import time
import json
import threading
from PIL import Image
from flask_pymongo import PyMongo
from pymongo import MongoClient
from bson.objectid import ObjectId
from flask import (
    Flask, 
    jsonify, 
    request,
    redirect, 
    Response, 
    render_template,
    url_for,
    send_from_directory, 
    abort
)

import process.init
from process.find_target import findTarget
from process.get_class import getClass
from process.set_target import featureCount
from process.set_target import extractColor
from process.set_colors import setColors
from process.test_target import testTarget
from process.get_target import getTarget

# Initialize Flask application
app = Flask(__name__, static_url_path='')
# basedir = os.path.abspath(os.path.dirname(__file__))

# Initialize MongoDB Atlas URL
client = MongoClient('mongodb+srv://datahub:techdemons@sih.of003.mongodb.net/SIH')
db = client["sih"]

# GET Route => Home Page
@app.route('/', methods=['GET'])
def home():
    return render_template("home.html")

@app.route('/newcase', methods=['POST'])
def New_Case():
    try:
        name = request.json['name']
    except:
        name = "Mystery"

    data = {
        "name": name,
        "class": None,
        "target": {
            "status": 0,
            "sides": None
        },
        "analysis": None
    }
    rec = client.db.cases.insert_one(data)
    caseID = rec.inserted_id
    return jsonify({'name': name, 'caseID': str(caseID)}), 200

# To select a bag inorder to Set a Target
@app.route('/findtarget', methods=['POST'])
def Find_Target():
    isID = 0
    
    try:
        ID = request.json['id']
        imgID = request.json['imgID']
        isID = ID
    except:
        image = request.files['image']
    

    if(isID > 0):
        temp_path = "./static/temporary/{}.jpg".format(imgID)
        # 
    else:
        filename = image.filename
        cur_time = str(int(time.time()))
        temp_name = "{}-{}".format(cur_time, filename)

        temp_path = "./static/temporary/{}".format(temp_name)
        image.save("./static/temporary/{}".format(temp_name))

    img, num, bags = findTarget(temp_path, isID)

    os.remove(temp_path)

    cur_time = str(int(time.time()))
    temp_name = cur_time + ".jpg"

    cv2.imwrite("./static/temporary/" + str(temp_name), img)
    link = "http://localhost:5000/temporary/{}".format(temp_name)

    if(isID > 0):
        res = {
            "img_link": link,
            "bag_info": bags
        }
    else:    
        res = {
            "img_link": link,
            "bags_count": num,
            "bags_detected": bags
        }
    
    return jsonify(res), 200

# Set Target Method
@app.route('/settarget', methods=['POST'])
def Set_Target():
    try:
        caseID = request.headers['caseID']
    except:
        return jsonify({"error": "'caseID' header file record is missing"})  

    if(not ObjectId.is_valid(caseID)):
        return jsonify({"error": "invalid case ID"})

    case = client.db.cases.find_one({'_id': ObjectId(caseID)})

    if (not case):
        return jsonify({"error": "invalid case ID"})

    try:
        side = request.args.get('side')
        if(side == None):
            return jsonify({"error": "please provide the valid parameters (side, image)"})
        elif(side != "front" and side != "back" and side != "left" and side != "right"):
            return jsonify({"error": "please provide the valid side option (front, back, left or right)"})
        image = request.files['image']
    except:
        return jsonify({"error": "please provide the valid parameters (side, image)"}) 

    # store the image with side name
    if(not os.path.isdir("./static/images/{}".format(caseID))):
        os.mkdir("./static/images/{}".format(caseID))

    img_name = str(side) + ".jpg"
    img_path = "./static/images/{}/{}".format(caseID,img_name)
    image.save(img_path)

    # extract class
    count, class_name = getClass(img_path)

    # if(count != 1):
    #     if(count == 0):
    #         return jsonify({"error": "image provided cannot be used as a target"})
    #     else:    
    #         return jsonify({"error": "image provided contains more than 1 bag"})

    img_class = case['class']

    if(img_class):
        if(img_class != class_name):
            return jsonify({"error": "bag category mismatch"})

    # extract features
    ln = featureCount(img_path)

    # if(ln < 10):
        # return jsonify({"error": "image provided cannot be used as a target because of low quality"})
    
    # extract colors
    clrs = extractColor(img_path)
    
    # save data into the database
    new_side = {
        "side": side,
        "colors": clrs,
        "status": 0
    }

    sides = case['target']['sides']
    
    if(not sides):
        new_sides = [new_side]
    else:
        for s in sides:
            if(s['side'] == side):
                sides.remove(s)
                break    
        sides.append(new_side)
        new_sides = sides

    update = {
        "class": "suitcase",
        "target": {
            "status": 0,
            "sides": new_sides
        }
    }

    client.db.cases.update_one({'_id': ObjectId(caseID)}, {'$set': update})

    # response the data
    link = "http://localhost:5000/images/{}/{}".format(caseID,img_name)

    res = {
        "features_found": ln,
        "colors": clrs,
        "img_link": link,
        "side": side
    }
    
    return jsonify(res), 200

# Set Target Colors Method
@app.route('/setcolor', methods=['POST'])
def Set_Color():
    try:
        caseID = request.headers['caseID']
    except:
        return jsonify({"error": "'caseID' header file record is missing"})  

    if(not ObjectId.is_valid(caseID)):
        return jsonify({"error": "invalid case ID"})

    case = client.db.cases.find_one({'_id': ObjectId(caseID)})

    if (not case):
        return jsonify({"error": "invalid case ID"})

    try:
        side = request.json['side']
        if(side == None):
            return jsonify({"error": "please provide the valid parameters (side)"})
        elif(side != "front" and side != "back" and side != "left" and side != "right"):
            return jsonify({"error": "please provide the valid side option (front, back, left or right)"})
        selectedID = request.json['selectedID'] 
        if(len(selectedID) > 7 or len(selectedID) == 0):
            return jsonify({"error": "invalid length of the selected color IDs"})
    except:
        return jsonify({"error": "please provide the valid parameters (side, selecteID)"})

    sides = case['target']['sides']

    temp_side = None

    other_sides = []

    for s in sides:
        if(s['side'] == side):
            temp_side = s
        else:
            other_sides.append(s)

    if(not temp_side):
        return jsonify({"error": "no such target side found in this case"})

    if(temp_side['status']):
        return jsonify({"error": "color for this side of the target has already filtered"})

    temp_clrs = temp_side['colors']
    temp_count = len(selectedID)

    new_clrs = []

    for c in temp_clrs:
        if c['id'] in selectedID:
            new_clrs.append(c)
            selectedID.remove(c['id'])

    if(len(selectedID) > 0 or len(new_clrs) != temp_count):
        return jsonify({"error": "selcted ids provided are wrong"})

    updated_clrs = setColors(new_clrs)  

    updated_side = {
        "side": side,
        "status": 1,
        "colors": updated_clrs
    }  

    other_sides.append(updated_side)

    isReady = 1

    for s in other_sides:
        if s['status'] == 0:
            isReady = 0

    updated_target = {
        "status": isReady,
        "sides": other_sides
    }        

    update = {
        "target": updated_target
    }

    client.db.cases.update_one({'_id': ObjectId(caseID)}, {'$set': update})

    return jsonify({"message": "success", "res": updated_target})

# Test target
@app.route('/testtarget', methods=['POST'])
def Test_Target():
    try:
        caseID = request.headers['caseID']
    except:
        return jsonify({"error": "'caseID' header file record is missing"})  

    if(not ObjectId.is_valid(caseID)):
        return jsonify({"error": "invalid case ID"})

    case = client.db.cases.find_one({'_id': ObjectId(caseID)})

    if (not case):
        return jsonify({"error": "invalid case ID"})

    if(not case['target']['status']):
        return jsonify({"error": "first please set the target properly to perform further detections"})

    try:
        image = request.files['image']
    except:
        return jsonify({"error": "please provide the valid parameter (image)"})

    filename = image.filename
    cur_time = str(int(time.time()))
    img_name = "{}-{}".format(cur_time, filename)

    img_path = "./static/images/{}/{}".format(caseID,img_name)
    image.save(img_path)

    target_class = case['class']
    target = case['target']

    res_img = testTarget(img_path, target_class, target, caseID)

    os.remove(img_path)

    cur_time = str(int(time.time()))
    temp_name = cur_time + ".jpg"

    cv2.imwrite("./static/temporary/" + str(temp_name), res_img)
    link = "http://localhost:5000/temporary/{}".format(temp_name)

    return jsonify({'link': link})


@app.route('/gettarget', methods=['POST'])
def Get_Target():
    try:
        caseID = request.headers['caseID']
    except:
        return jsonify({"error": "'caseID' header file record is missing"})  

    if(not ObjectId.is_valid(caseID)):
        return jsonify({"error": "invalid case ID"})

    case = client.db.cases.find_one({'_id': ObjectId(caseID)})

    if (not case):
        return jsonify({"error": "invalid case ID"})

    if(not case['target']['status']):
        return jsonify({"error": "first please set the target properly to perform further detections"})

    # try:
    #     video = request.files['video']
    # except:
    #     return jsonify({"error": "please provide the valid parameter (video)"})

    # store the video in its caseID folder
    if(not os.path.isdir("./static/videos/{}".format(caseID))):
        os.mkdir("./static/videos/{}".format(caseID))

    # filename = video.filename
    # cur_time = str(int(time.time()))
    # vid_name = "{}-{}".format(cur_time, filename)

    # vid_path = "./static/videos/{}/{}".format(caseID,vid_name)
    # video.save(vid_path)

    vid_path = "./process/train_Trim.mp4"

    target = case['target']

    # getTarget(vid_path, target, caseID)

    t = threading.Thread(target=getTarget, args=[vid_path, target, caseID])
    t.start()

    link = "http://35.225.41.24/videos/{}/output.avi".format(caseID)

    return jsonify({"message": "started the process", "link": link}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True, port=5000)

    # 5f1431a9849cbc57c04dcb04