#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Your task is to wrangle the data and transform the shape of the data
into the model we mentioned earlier. The output should be a list of dictionaries
that look like this:

{
"id": "2406124091",
"type: "node",
"visible":"true",
"created": {
          "version":"2",
          "changeset":"17206049",
          "timestamp":"2013-08-03T16:43:42Z",
          "user":"linuxUser16",
          "uid":"1219059"
        },
"pos": [41.9757030, -87.6921867],
"address": {
          "housenumber": "5157",
          "postcode": "60625",
          "street": "North Lincoln Ave"
        },
"amenity": "restaurant",
"cuisine": "mexican",
"name": "La Cabana De Don Luis",
"phone": "1 (773)-271-5176"
}

You have to complete the function 'shape_element'.
We have provided a function that will parse the map file, and call the function with the element
as an argument. You should return a dictionary, containing the shaped data for that element.
We have also provided a way to save the data in a file, so that you could use
mongoimport later on to import the shaped data into MongoDB.

Note that in this exercise we do not use the 'update street name' procedures
you worked on in the previous exercise. If you are using this code in your final
project, you are strongly encouraged to use the code from previous exercise to
update the street names before you save them to JSON.

In particular the following things should be done:
- you should process only 2 types of top level tags: "node" and "way"
- all attributes of "node" and "way" should be turned into regular key/value pairs, except:
    - attributes in the CREATED array should be added under a key "created"
    - attributes for latitude and longitude should be added to a "pos" array,
      for use in geospacial indexing. Make sure the values inside "pos" array are floats
      and not strings.
- if second level tag "k" value contains problematic characters, it should be ignored
- if second level tag "k" value starts with "addr:", it should be added to a dictionary "address"
- if second level tag "k" value does not start with "addr:", but contains ":", you can process it
  same as any other tag.
- if there is a second ":" that separates the type/direction of a street,
  the tag should be ignored, for example:

<tag k="addr:housenumber" v="5158"/>
<tag k="addr:street" v="North Lincoln Avenue"/>
<tag k="addr:street:name" v="Lincoln"/>
<tag k="addr:street:prefix" v="North"/>
<tag k="addr:street:type" v="Avenue"/>
<tag k="amenity" v="pharmacy"/>

  should be turned into:

{...
"address": {
    "housenumber": 5158,
    "street": "North Lincoln Avenue"
}
"amenity": "pharmacy",
...
}

- for "way" specifically:

  <nd ref="305896090"/>
  <nd ref="1719825889"/>

should be turned into
"node_refs": ["305896090", "1719825889"]
"""


import xml.etree.ElementTree as ET
import pprint
import re
import codecs
import json


LOWER = re.compile(r'^([a-z]|_)*$')
LOWER_COLON = re.compile(r'^([a-z]|_)*:([a-z]|_)*$')
PROBLEM_CHARS = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')

CREATED = ["version", "changeset", "timestamp", "user", "uid"]
POSITION = ["lat", "lon"]


def process_map(file_in, pretty=False):
    """Transform XML data into JSON document schema for mongodb upload"""
    file_out = "{0}.json".format(file_in)
    data = []
    with codecs.open(file_out, "w") as fo:
        for _, element in ET.iterparse(file_in):
            el = shape_element(element)
            if el:
                data.append(el)
                if pretty:
                    fo.write(json.dumps(el, indent=2)+"\n")
                else:
                    fo.write(json.dumps(el) + "\n")
    return data


def shape_element(element):
    """Transform XML element into dictionary representation"""
    node = {}

    if element.tag == "node" or element.tag == "way":
        node["type"] = element.tag
        # Add desired element attributes to node
        node = transform_element_attributes(node, element)

        # Add desired sub-element attributes to node
        node = transform_sub_elem_attributes(node, element)

        return node
    else:
        return None


def transform_element_attributes(node, element):
    """Transform and add element attributes to node"""
    #Get all attributes of XML element.
    attributes = element.attrib

    for attribute in attributes:
        value = element.attrib[attribute]
        #Capture special attrs in CREATED collection and add to nested dict.
        if attribute in CREATED:
            if "created" not in node:
                node["created"] = {}
            node["created"][attribute] = value
        #Capture lat, lon  attributes and add to nested dict "pos".
        elif attribute in POSITION:
            if "pos" not in node:
                node["pos"] = []
            #Ensure proper order of lat, lon in list.
            if attribute == "lat":
                node["pos"].insert(0, float(value))
            else:
                node["pos"].append(float(value))
        else:
            #Place attribute in dict.
            node[attribute] = value

    return node


def transform_sub_elem_attributes(node, element):
    """Transform and add sub elements to node"""
    sub_elements = element.getiterator()

    for sub_elm in sub_elements:
        if sub_elm.tag == "tag":
            node = transform_tag_elem(node, sub_elm)

        if sub_elm.tag == "nd":
            node = transform_nd_tag(node, sub_elm)

    return node


def transform_tag_elem(node, sub_elem):
    """Extracts and adds tag element specific attributes"""
    k_val = sub_elem.attrib["k"]
    v_val = sub_elem.attrib["v"]

    #Catch and ignore problematic k values.
    if contains_bad_char(k_val) or is_compound_street_address(k_val):
        return node

    #Catch address related k values.
    if k_val.startswith("addr:"):
        if "address" not in node:
            node["address"] = {}

        values = k_val.split(":")
        key = values[1]
        node["address"][key] = v_val
    else:
        node[k_val] = v_val

    return node


def transform_nd_tag(node, sub_elm):
    """Extracts and adds nd tag specific attributes"""
    ref = sub_elm.attrib["ref"]

    if "node_refs" in node:
        node["node_refs"].append(ref)
    else:
        node["node_refs"] = [ref]

    return node


def is_compound_street_address(string):
    """Returns true if string is a compound address"""
    values = string.split(":")
    if len(values) > 2 and values[1] == "street":
        return True

    return False


def contains_bad_char(string):
    """Returns true if string contains problematic characters"""
    return re.search(PROBLEM_CHARS, string)


def test():
    """Test process_map function"""
    # NOTE: if you are running this code on your computer, with a larger dataset,
    # call the process_map procedure with pretty=False. The pretty=True option adds
    # additional spaces to the output, making it significantly larger.
    data = process_map('example.osm', True)
    #pprint.pprint(data)

    correct_first_elem = {
        "id": "261114295",
        "visible": "true",
        "type": "node",
        "pos": [41.9730791, -87.6866303],
        "created": {
            "changeset": "11129782",
            "user": "bbmiller",
            "version": "7",
            "uid": "451048",
            "timestamp": "2012-03-28T18:31:23Z"
        }
    }
    assert data[0] == correct_first_elem
    assert data[-1]["address"] == {
        "street": "West Lexington St.",
        "housenumber": "1412"
    }
    assert data[-1]["node_refs"] == ["2199822281", "2199822390", "2199822392", "2199822369",
                                     "2199822370", "2199822284", "2199822281"]


if __name__ == "__main__":
    test()
