"""API for print card data"""

from flask import jsonify, Blueprint
import lxml.etree as ET  # to parse xml file
import datetime
from mainapp.procon.apps.transaction import Transaction
from mainapp.procon.apps.cm_config import CNSTR_ADPUBK, UBK_INTERFACE_DEV

api = Blueprint('procon', __name__)  # add blueprint


@api.route('/material/<material_number>')
def main(material_number):
    # get the xml string from the response
    xml = get_xml(material_number)

    # parse the xml file to return oxygen & wire material nums
    oxygen_material_num, wire_material_num, message = parse_xml(xml)

    # jsonify the data
    data = create_json(oxygen_material_num, wire_material_num, message)

    return data

# Requests BOM from SAP
def get_xml(material_number):
    bom_cfg = {
        'description': 'Modified', # modified for security reasons
        'app_id': 1,  # Application Id in the UBK System, modified for security reasons
        'cnx_str': 1,  # connection string for the process database, modified for security reasons
        'count_pt': 1, # modified for security reasons
        'target_sys': 1,  # UBK_INTERFACE target system, modified for security reasons
        'template_id': 1,  # Transaction template Id, modified for security reasons
        # Default parameters in the UBK, all modified for security reasons
        'default_params': [
            ('//BomAlternative', '1'), 
            ('//Plant', '1'),
            ('//BomStatus', '1'),
            ('//BomUsage', '1'),
            ('//BomStlIndicator', '1'),
            ('//Application', '1'),
            ('//IndicatorBomExplosionLevel', '1'),

        ],
        # Map of XML to part attribute names
        'variable_params': [
            ('//MaterialNumber', 'MaterialNumber'),
            ('//ExplosionDate', 'ExplosionDate')
        ],
        # Returns the response with the Request
        'rtn_pkt': 1
        # Part numbers to collect
    }

    trx = Transaction(cfg=bom_cfg)
    part_like_object = {'MaterialNumber': material_number,
                        'ExplosionDate': datetime.datetime.now().strftime('%Y-%m-%d')}
    trx.create_payload(part=part_like_object, overrides=None)

    trx.send_to_ubk(batch=None)

    return trx.response['response_pkt']

# Parse the XML response
def parse_xml(xml):
    oxygen_material_num = None
    wire_material_num = None
    errorMessage = "Error when parsing for oxygen and wire material number from the BOM from SAP."
    okMessage = "OK"

    # parsing the XML in the form of a string
    try:
        root = ET.fromstring(xml)

    except ET.ParseError as e:
        return oxygen_material_num, wire_material_num, errorMessage
    except Exception as e:
        # Handle other exceptions that may occur during parsing
        return oxygen_material_num, wire_material_num, errorMessage

    # loop through all children of root
    for child in root[1][0]:

        # if child is Bom and levnum, materical_desc, prod_rel, and materialNum tags exist
        if (child.tag == 'Bom' and child.find('IndicatorItemRelevantToProduction') is not None
                and child.find('DepthOfProdStructure') is not None
                and child.find('MaterialDescription') is not None
                and child.find('MaterialNumber') is not None):

            levnum = child.findall('DepthOfProdStructure')[0].text
            material_desc = child.findall('MaterialDescription')[0].text
            prod_rel = child.findall('IndicatorItemRelevantToProduction')[0].text
            material_num = child.findall('MaterialNumber')[0].text

            # making material desc lowercase to compare
            lowercase_material = material_desc.lower()
            # if level is 1 or 2 and oxygen sensor vorm or wiring harness is in desc and production relative is X
            if ((levnum == '.1' or levnum == '..2') and (
                    ("oxygen sensor" in lowercase_material and "vorm" in lowercase_material) or
                    "wiring harness" in lowercase_material) and prod_rel == 'X'):

                if "oxygen sensor" in lowercase_material and "vorm" in lowercase_material:
                    oxygen_material_num = material_num
                if "wiring harness" in lowercase_material:
                    wire_material_num = material_num

    # add to the message if the oxygen or wire weren't found
    if oxygen_material_num == None and wire_material_num == None:
        message = 'Oxygen sensor and wire harness material number was not found.'
        return oxygen_material_num, wire_material_num, message
    elif oxygen_material_num == None:
        message = 'Oxygen material number was not found.'
        return oxygen_material_num, wire_material_num, message
    elif wire_material_num == None:
        message = 'Wire material number was not found.'
        return oxygen_material_num, wire_material_num, message

    return oxygen_material_num, wire_material_num, okMessage

# Create the JSON format for the api and return it
def create_json(oxygen_material_num, wire_material_num, message):
    data = {
        'Oxygen Sensor': oxygen_material_num,
        'Wire Harness': wire_material_num,
        'Message': message
    }
    return jsonify(data)
