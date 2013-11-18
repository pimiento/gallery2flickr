#!/usr/bin/env python2
# -*- coding: utf-8 -*-
import os
import urllib2
from lxml import html
from configuration import *
from mylog import my_log, LOG_FILE
from flickrapi import FlickrAPI, FlickrError


def get_flickr():
    if TOKEN is None:
        flickr = FlickrAPI(API_KEY, SECRET)
        (token, frob) = flickr.get_token_part_one(perms='write')
        if not token:
            raw_input("Press ENTER after you authorized this program")
        flickr.get_token_part_two((token, frob))
    else:
        flickr = FlickrAPI(API_KEY, SECRET, TOKEN)
    return flickr

flickr = get_flickr()

def already_created(filename=LOG_FILE):
    try:
        content = open(filename, 'r')
    except IOError:
        raise IOError("There is no log-file %s" % filename)
    else:
        global UPLOADED
        global PHOTOSETS
        global COLLECTIONS
        UPLOADED = {}
        PHOTOSETS = {}
        COLLECTIONS = {}
        for log_line in content:
            date, info = log_line.split('-:-')
            line = info.replace('\\n', '\n')
            flag, title, obj_path = line.split(":::")
            if "photo" in flag:
                UPLOADED[title] = obj_path
            elif "album" in flag:
                PHOTOSETS[title] = obj_path
            elif "collection" in flag:
                COLLECTIONS[title] = obj_path
    finally:
        content.close()


get_class_content = lambda elem, class_name: reduce(lambda x,y: x + " " + y,
                                                    map(lambda x:x.text_content().strip(),
                                                        elem.find_class(class_name)),
                                                    "").strip()

get_link = lambda elem: elem.find('./div/a').attrib['href']
get_tree = lambda link: html.fromstring(urllib2.urlopen(DOMAIN + link).read())
get_image = lambda tree: DOMAIN + tree.find('.//div[@id="gsImageView"]').find('img').attrib['src']


def get_image_link(tree):
    image_link = None
    try:
        image_link = get_image(tree)
    except AttributeError:
        # probably there is video instead of image
        image_link = tree.find('.//div[@id="gsImageView"]//param[@name=\"FileName\"]').attrib['value']
    return image_link

def get_items_cells(link):
    tree = get_tree(link)
    items = tree.find_class('giItemCell')
    return items, tree

def additional_items(span_list):
    items_list = []
    for span in span_list:
        # it isn't span for current page
        if span.find('a') is not None:
            items_cells, _ = get_items_cells(span.find('a').attrib['href'])
            items_list += items_cells
    return items_list

def get_file(item, commint=True):
    link = item['image']
    filename = os.path.basename(link)
    if not commint:
        return filename
    download_file = urllib2.urlopen(link).read()
    with open(filename, 'w') as fn:
        fn.write(download_file)
    return filename

def create_photoset(title, description, album_data):
    if title in PHOTOSETS:
        print('%s is already created' % title)
        photoset_id = PHOTOSETS[title]
    else:
        photoset = flickr.photosets_create(title=title, description=description,
                                           primary_photo_id=album_data[0][0]).getchildren()[0]
        photoset_id = photoset.attrib['id']
        print('creating photoset %s (%s)' % (title, photoset_id))
        my_log('album:::%s:::%s' % (title, photoset_id))

    for photo in album_data[1:]:
        try:
            flickr.photosets_addPhoto(photoset_id=photoset_id, photo_id=photo[0])
        except FlickrError:
            continue
        print('adding photo %s to photoset %s' % (photo[0], photoset_id))
    return photoset_id

def create_items(items_data, album):
    result = []
    for item in items_data:
        filename = get_file(item, commint=False)
        if item['title'] in UPLOADED:
            print('%s is already uploaded' % item['title'])
            photo_id = UPLOADED[item['title']]
        elif filename in UPLOADED:
            print('%s is already uploaded' % filename)
            photo_id = UPLOADED[filename]
        else:
            upload_file = get_file(item)
            photo_id = flickr.upload(filename=upload_file, title=item['title'],
                                 description=item['description']).find('photoid').text
            print('uploading photo %s (%s)' % (item['title'], photo_id))
            my_log('photo:::%s:::%s' % (upload_file, photo_id))
            os.unlink(upload_file)
            dl = item['date'].split('/')
            date = "%s-%s-%s" % (dl[2], dl[0], dl[1])
            flickr.photos_setDates(photo_id=photo_id, date_posted=date)
        result.append([photo_id, item['title'], item['description']])
    return result

def get_album_data(album, fast=FAST_MODE):
    description = get_class_content(album, 'giDescription')
    title = get_class_content(album, 'giTitle').split(":")[1].strip()
    link = get_link(album)
    date = get_class_content(album, 'date').split(":")[1].strip()
    if description.lower() == 'no description':
        description = date
    inner_tree = get_tree(link)
    inner_albums = inner_tree.find_class('giAlbumCell')
    if fast:
        if title in PHOTOSETS:
            print('%s is already created' % title)
            return PHOTOSETS[title]
        elif title in COLLECTIONS:
            print("collection %s is already created" % title)
            return COLLECTIONS[title]
    if bool(inner_albums):
        # Superocollection
        print("photoset %s contains another photosets" % title)
        inner_albums = map(get_album_data, inner_albums)
        if title in COLLECTIONS:
            print("collection %s is already created" % title)
            return COLLECTIONS[title]
        else:
            collection_id = flickr.collections_create(title=title, description=description).getchildren()[0].attrib['id']
            print("create collection %s (%s)" % (title, collection_id))
            my_log('collection:::%s:::%s' % (title, collection_id))
            flickr.collections_editSets(collection_id=collection_id, photoset_ids=','.join(inner_albums))
            return collection_id
    else:
        album_data = get_album_inner_data(link, description)
        photoset = create_photoset(title, description, album_data)
        return photoset

def get_album_inner_data(link, album_description):
    items, tree = get_items_cells(link)
    additional_pages = tree.find('.//div[@id="gsPages"]')
    if additional_pages is not None:
        items_plus = additional_items(additional_pages.getchildren()[0].getchildren())
        items += items_plus
    items_data = map(get_item_data, items)
    items_id = create_items(items_data, album_description)
    return items_id

def get_item_data(item):
    title = get_class_content(item, 'giTitle')
    item_link = get_link(item)
    data = get_data(item_link)
    return dict(title=title, **data)

def get_data(link):
    tree = get_tree(link)
    full_size = tree.find('.//a[@title=\"Full Size\"]')
    if full_size is not None:
        description_block = tree.find_class('giInfo')[0]
        image_link = full_size.attrib['href']
    else:
        description_block = tree.find_class('gcBackground1')[0]
        image_link = description_block.find(".//a")

    date = get_class_content(description_block, 'date').split(":")[1]
    owner = get_class_content(description_block, 'owner').split(":")[1]
    description = get_class_content(description_block, 'giDescription')

    if image_link is None:
        image_link = get_image_link(tree)
    elif full_size is not None:
        image_link = DOMAIN + image_link
    else:
        # get original sized image
        original_size_link = DOMAIN + image_link.attrib['href']
        new_tree = get_tree(link)
        image_link = get_image_link(new_tree)
    return dict(date=date.strip(),owner=owner.strip(),description=description,
                image=image_link.strip())

def main():
    gallery_url = GALLERY
    main_page = get_tree(gallery_url)
    albums = main_page.find_class("giAlbumCell")
    already_created()
    albums_data = map(get_album_data, albums)
    print albums_data

if __name__ == "__main__":
    main()
