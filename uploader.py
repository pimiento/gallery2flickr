#!/usr/bin/env python2
import os
import sys
import urllib2
from mylog import my_log
from configuration import *
from itertools import groupby
from flickrapi import FlickrError

ALBUM_LOG = ""

flickr = get_flickr(API_KEY, SECRET, TOKEN)
is_dir = lambda path: lambda x: os.path.isdir(os.path.join(path, x))

def update_log(path, obj_id):
    with open(ALBUM_LOG, "a") as al:
        al.write("%s:::%s\n" % (path, obj_id))

def already_uploaded(logfile):
    global UPLOADED
    if os.path.isfile(logfile):
        UPLOADED = parse_meta(logfile)
    else:
        UPLOADED = {}

def parse_meta(path):
    with open(path, 'r') as mfd:
        meta = mfd
        res_dict = {}
        for k,v in [x.strip().split(":::") for x in meta]:
            res_dict[k] = v.replace('\\n', '\n')
    return res_dict


def get_type(path):
    isdir = is_dir(path)
    if len(filter(isdir, os.listdir(path))) == 0:
        real_type = "album"
    else:
        real_type = "collection"
    return real_type


def uploader(path):
    return {'album': album_uploader,
            'collection': collection_uploader}[get_type(path)](path)


def photo_uploader(path):
    data = parse_meta(path+'.meta')
    if data['path'] in UPLOADED:
        print("Item %s is already uploaded" % data['path'])
        return UPLOADED[data['path']]

    photo_id = flickr.upload(filename=data['path'], title=data['title'],
                             description=data['description']).find('photoid').text
    update_log(data['path'], photo_id)
    my_log('photo:::%s:::%s' % (data['title'], photo_id))
    dl = data['date'].split('/')
    date = "%s-%s-%s" % (dl[2], dl[0], dl[1])
    flickr.photos_setDates(photo_id=photo_id, date_posted=date)
    return photo_id


def album_uploader(path):
    data = parse_meta(os.path.join(path, 'meta'))
    if data['type'] != "album":
        print("ALARM! UVAGA! meta contains wrong information! %s" % path)
        data['type'] = "album"
    if data['dir'] in UPLOADED:
        print("Album %s is already uploaded" % data['dir'])
        return UPLOADED[data['dir']]
    photos = []

    # At first we have to download photos from that album
    # and after create photoset for that photos
    for photo in filter(lambda x: not x.endswith('meta') and x != "log",
                        os.listdir(path)):
        photo_path = os.path.join(path, photo)
        photo_id = photo_uploader(photo_path)
        photos.append(photo_id)

    photoset_id = flickr.photosets_create(
        title=data['title'], description=data['description'],
        primary_photo_id=photos[0]).getchildren()[0].attrib['id']
    update_log(data['dir'], photoset_id)
    my_log('album:::%s:::%s' % (data['title'], photoset_id))

    # we already added first photo into the photoset and add another n-1
    for photo_id in photos[1:]:
        try:
            flickr.photosets_addPhoto(photoset_id=photoset_id, photo_id=photo_id)
        except FlickrError, e:
            print e

    return photoset_id


def collection_uploader(path):
    data = parse_meta(os.path.join(path, 'meta'))
    if data['dir'] in UPLOADED:
        print("Collection %s is already uploaded")
        return UPLOADED[data['dir']]

    inners = []
    isdir = is_dir(path)
    for inner in filter(isdir, os.listdir(path)):
        inner_path = os.path.join(path, inner)
        inner_id = uploader(inner_path)
        inners.append(inner_id)

    collection_id = flickr.collections_create(title=data['title'],
                                              description=data['description']
                                              ).getchildren()[0].attrib['id']
    update_log(data['dir'], collection_id)
    my_log('collection:::%s:::%s' % (data['title'], collection_id))

    flickr.collections_editSets(collection_id=collection_id,
                                photoset_ids=','.join(inners))
    return collection_id


if __name__=="__main__":
    path = sys.argv[1]
    ALBUM_LOG = os.path.join(path, 'log')
    already_uploaded(ALBUM_LOG)
    uploader(path)
