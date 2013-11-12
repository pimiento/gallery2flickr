#!/usr/bin/env python2
# -*- coding: utf-8 -*-
import os
import urllib2
from lxml import html
from flickrapi import FlickrAPI

DOMAIN = "http://example.com"
get_class_content = lambda elem, class_name: reduce(lambda x,y: x + " " + y,
                                                    map(lambda x:x.text_content().strip(),
                                                        elem.find_class(class_name)),
                                                    "").strip()

get_link = lambda elem: elem.find('./div/a').attrib['href']

get_tree = lambda link: html.fromstring(urllib2.urlopen(DOMAIN + link).read())

get_image = lambda tree: DOMAIN + tree.find('.//div[@id="gsImageView"]').find('img').attrib['src']

API_KEY = "key"
SECRET = "secret"

flickr = FlickrAPI(API_KEY, SECRET)
(token, frob) = flickr.get_token_part_one(perms='write')
if not token:
    raw_input("Press ENTER after you authorized this program")
flickr.get_token_part_two((token, frob))

def get_file(item):
    link = item['image']
    filename = os.path.basename(link)
    download_file = urllib2.urlopen(link).read()
    with open(filename, 'w') as fn:
        fn.write(download_file)
    return filename

def create_album(title, description, collection_data):
    print("Creating album \"%s\"" % title)
    photoset = flickr.photosets_create(title=title, description=description,
                                       primary_photo_id=collection_data[0][0]).getchildren()[0]
    photoset_id = photoset.attrib['id']
    for photo in collection_data[1:]:
        flickr.photosets_addPhoto(photoset_id=photoset_id, photo_id=photo[0])

def create_items(items_data, album):
    result = []
    for item in items_data:
        upload_file = get_file(item)
        photo_id = flickr.upload(filename=upload_file, title=item['title'],
                                 description=item['description']).find('photoid').text
        os.unlink(upload_file)
        dl = item['date'].split('/')
        date = "%s-%s-%s" % (dl[2], dl[0], dl[1])
        flickr.photos_setDates(photo_id=photo_id, date_posted=date)
        result.append([photo_id, item['title'], item['description']])
    return result

def get_album_data(album):
    description = get_class_content(album, 'giDescription')
    title = get_class_content(album, 'giTitle').split(":")[1].strip()
    link = get_link(album)
    date = get_class_content(album, 'date').split(":")[1].strip()
    if description.lower() == 'no description':
        description = date
    collection_data = get_collection_data(link, description)
    create_album(title, description, collection_data)
    return collection_data

def get_collection_data(link, album_description):
    tree = get_tree(link)
    items = tree.find_class('giItemCell')
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
    description_block = tree.find_class('gcBackground1')[0]
    date = get_class_content(description_block, 'date').split(":")[1]
    owner = get_class_content(description_block, 'owner').split(":")[1]
    description = get_class_content(description_block, 'giDescription')
    image_link = description_block.find(".//a")
    if image_link is None:
        image_link = get_image(tree)
    else:
        # get original sized image
        original_size_link = DOMAIN + image_link.attrib['href']
        new_tree = get_tree(link)
        image_link = get_image(new_tree)
    return dict(date=date.strip(),owner=owner.strip(),description=description,
                image=image_link.strip())

def main():
    gallery_url = "/gallery/v/mygallery"
    main_page = get_tree(gallery_url)
    albums = main_page.find_class("giAlbumCell")
    albums_data = map(get_album_data, albums)
    print albums_data

if __name__ == "__main__":
    main()
