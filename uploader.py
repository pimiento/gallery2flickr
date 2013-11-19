#!/usr/bin/env python2
import os
import sys
import urllib2
from mylog import my_log
from configuration import *
from itertools import groupby
from flickrapi import FlickrError

flickr = get_flickr(API_KEY, SECRET, TOKEN)

def parse_meta(path):
    with open(os.path.join(path), 'r') as mfd:
        meta = mfd
        res_dict = {}
        for k,v in [x.strip().split(":::") for x in meta]:
            res_dict[k] = v.replace('\\n', '\n')
    return res_dict


def get_type(path):
    if len(filter(os.path.isdir, os.listdir(path))) == 0:
        real_type = "album"
    else:
        real_type = "collection"
    return real_type


def uploader(path):
    {'album': album_uploader,
     'collection': collection_uploader}[get_type(path)](path)


def photo_uploader(path):
    data = parse_meta(path+'.meta')
    print data
    photo_id = flickr.upload(filename=data['path'], title=data['title'],
                             description=data['description']).find('photoid').text
    print('uploading photo %s (%s)' % (data['title'], photo_id))
    my_log('photo:::%s:::%s' % (data['title'], photo_id))
    dl = data['date'].split('/')
    date = "%s-%s-%s" % (dl[2], dl[0], dl[1])
    flickr.photos_setDates(photo_id=photo_id, date_posted=date)
    return photo_id


def album_uploader(path):
    data = parse_meta(os.path.join(path, 'meta'))
    # At first we have to download photos from that album
    # and after create photoset for that photos
    if data['type'] != "album":
        print("ALARM! UVAGA! meta contains wrong information! %s" % path)
        data['type'] = "album"
    photos = []

    # upload all photos from album
    for photo in filter(lambda x: not x.endswith('meta'), os.listdir(path)):
        photo_path = os.path.join(path, photo)
        photo_id = photo_uploader(photo_path)
        photos.append(photo_id)

    photoset_id = flickr.photosets_create(
        title=data['title'], description=data['description'],
        primary_photo_id=photos[0]).getchildren()[0].attrib['id']
    my_log('album:::%s:::%s' % (title, photoset_id))

    # we already added first photo into the photoset and add another n-1
    for photo_id in photos[1:]:
        try:
            flickr.photosets_addPhoto(photoset_id=photoset_id, photo_id=photo_id)
        except FlickrError, e:
            print e
        print('adding photo %s to photoset %s' % (photo_id, photoset_id))
    return photoset_id


def collection_uploader(path):
    data = parse_meta(os.path.join(path))
    inners = []

    for inner in os.listdir(path):
        inner_path = os.join(path, inner)
        inner_id = uploader(inner_path)
        inners.append(inner_id)

    collection_id = flickr.collections_create(title=title,
                                              description=description
                                              ).getchildren()[0].attrib['id']
    print("create collection %s (%s)" % (title, collection_id))
    my_log('collection:::%s:::%s' % (title, collection_id))
    flickr.collections_editSets(collection_id=collection_id,
                                photoset_ids=','.join(inners))
    return collection_id


if __name__=="__main__":
    uploader(sys.argv[1])
