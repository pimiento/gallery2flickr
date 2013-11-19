#!/usr/bin/env python2
# -*- coding: utf-8 -*-
import os
import string
import urllib
import cPickle
import urllib2
from lxml import html
from configuration import *
from mylog import my_log, LOG_FILE

def upload_machine(path):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(script_dir, "uploader.py")
    for album in os.listdir(path):
        album_path = os.path.join(path, album)
        os.spawnlp(os.P_NOWAIT, script, script, album_path, "/dev/null")

get_class_content = lambda elem, class_name: reduce(lambda x,y: x + " " + y,
                                                    map(lambda x:x.text_content().strip(),
                                                        elem.find_class(class_name)),
                                                    "").strip()

get_link = lambda elem: elem.find('./div/a').attrib['href']
get_tree = lambda link: html.fromstring(urllib2.urlopen(DOMAIN + link).read())
get_name = lambda path: os.path.basename(path.rstrip("/"))
get_meta = lambda attributes: reduce(lambda x,y: x+"%s:::%s\n" % (y[0], y[1].replace('\n', '\\n')),
                                     attributes.iteritems(), "")
find_items = lambda tree: tree.find_class('giItemCell')
find_albums = lambda tree: tree.find_class('giAlbumCell')


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

class Item(object):

    def __init__(self, link, cur_dir):
        self.cur_dir = cur_dir
        self.link = link
        self.name = get_name(self.link)
        self.path = os.path.join(self.cur_dir, self.name)
        self.tree = get_tree(self.link)
        self.attributes = {'link': self.link, 'name': self.name,
                           'path': self.path}

    def run(self):
        self.title = get_class_content(self.tree, 'giTitle')
        self.update_data(self.get_data())
        self.write_file()
        return self

    def write_file(self):
        link = self.attributes['image']
        if not os.path.isfile(self.path):
            with open(self.path, 'w') as fd:
                fd.write(urllib2.urlopen(link).read())
            with open(self.path + ".meta", "w") as meta:
                meta.write(self.get_meta())
            my_log("File %s is writted" % self.path)

    def get_meta(self):
        return get_meta(self.attributes)

    def get_data(self):
        full_size = self.tree.find('.//a[@title=\"Full Size\"]')
        if full_size is not None:
            description_block = self.tree.find_class('giInfo')[0]
            image_link = full_size
        else:
            description_block = self.tree.find_class('gcBackground1')[0]
            image_link = description_block.find(".//a")

        date = get_class_content(description_block, 'date').split(":")[1]
        owner = get_class_content(description_block, 'owner').split(":")[1]
        description = get_class_content(description_block, 'giDescription')

        if image_link is None:
            image_link = self.get_image_link(self.tree)
        elif full_size is not None:
            image_link = DOMAIN + image_link.attrib['href']
        else:
            # get original sized image
            original_size_link = image_link.attrib['href']
            new_tree = get_tree(original_size_link)
            image_link = self.get_image_link(new_tree)
        return dict(date=date.strip(), owner=owner.strip(),
                    description=description, image=image_link.strip())

    def get_image_link(self, tree):
        image_link = None
        try:
            image_link = DOMAIN + tree.find('.//div[@id="gsImageView"]').find('img').attrib['src']
        except AttributeError:
            # probably there is video instead of image
            image_link = tree.find('.//div[@id="gsImageView"]//param[@name=\"FileName\"]').attrib['value']
        return image_link

    def update_data(self, data):
        for key, value in data.iteritems():
            self.attributes[key] = value

    def dumps(self):
        return self.attributes


class Album(object):

    def __init__(self, link, cur_dir="./", data={}):
        self.link = link
        self.name = get_name(self.link)
        self.cur_dir = os.path.join(cur_dir, self.name)
        self.tree = get_tree(link)
        attributes = data
        attributes['name'] = self.name
        attributes['dir'] = self.cur_dir
        self.attributes = attributes
        self.albums = []
        self.items = []

    def get_meta(self, cur_dir):
        attributes = self.attributes
        attributes['dir'] = cur_dir
        return get_meta(attributes)

    def run(self):
        if not os.path.isdir(self.cur_dir):
            os.mkdir(self.cur_dir)
            with open(os.path.join(self.cur_dir, "meta"), "w") as meta:
                meta.write(self.get_meta(self.cur_dir))
            my_log("Album %s created" % self.cur_dir)

        albums, items = self.get_albums_n_items()
        if len(albums) and len(items):
            # If album has another albums and sole items too
            # we should create album for that sole objects
            # because Flickr can not contain sole object with albums in a collection
            self.update_albums(albums)
            new_dir = os.path.join(self.cur_dir, self.name)
            if not os.path.isdir(new_dir):
                os.mkdir(new_dir)
                with open(os.path.join(new_dir, "meta"), "w") as meta:
                    meta.write(self.get_meta(new_dir))
            self.update_items(items, new_dir)
        elif len(albums):
            self.update_albums(albums)
        else:
            self.update_items(items, self.cur_dir)
        return self

    def update_albums(self, albums):
        for album in albums:
            link = get_link(album)
            album_data = self.get_album_data(album)
            _album = Album(link, cur_dir=self.cur_dir,
                           data=album_data)
            self.albums.append(_album.run())

    def update_items(self, items, cur_dir):
        for item in items:
            link = get_link(item)
            _item = Item(link, cur_dir)
            self.items.append(_item.run())

    def get_album_data(self, album):

        def gcc(string):
            try:
                return get_class_content(album, string).split(":")[1].strip()
            except IndexError:
                return ""

        description = gcc('giDescription')
        title = gcc('giTitle')
        date = gcc('date')
        size = gcc('size')
        if description.lower() == 'no description':
            description = ""
        return {'description': description, 'title': title,
                'date': date, 'size': size}

    def get_albums_n_items(self):
        albums = find_albums(self.tree)
        items = find_items(self.tree)
        additional_pages = self.tree.find('.//div[@id="gsPages"]')
        if additional_pages is not None and len(additional_pages):
            a_albums, a_items = self.additional_items(additional_pages.getchildren()[0].getchildren())
            albums += a_albums
            items += a_items
        return albums, items

    def additional_items(self, span_list):
        "Find items in another pages into that album"
        if span_list is None or not len(span_list):
            return [], []
        items_list = []
        albums_list = []
        for span in span_list:
            a = span.find('a')
            # it isn't span for current page
            if a is not None:
                tree = get_tree(a.attrib['href'])
                items_list += find_items(tree)
                albums_list += find_albums(tree)
        return albums_list, items_list

    def dumps(self):
        albums = []
        items = []
        for album in self.albums:
            albums.append(album.dumps())
        if len(self.items):
            for item in self.items:
                items.append(item.dumps())
        result = {'attributes': self.attributes,
                  'albums': albums,
                  'items': items}
        return cPickle.dumps(result)

    def get_type(self):
        return len(self.albums) == 0 and "album" or "collection"


def main():
    GALLERY="/gallery/v/ZhMPhotos/"
    album = Album(GALLERY)
    upload_machine(get_name(GALLERY))
    album.run()

if __name__ == "__main__":
    main()
