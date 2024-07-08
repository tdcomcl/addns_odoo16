# -*- coding: utf-8 -*-
{
    'name':'POS XML Receipt',
    'summary': 'Use XML Receipt for orders instead image print',
    'description':'Use XML Receipt for orders instead image print',
    'category': 'Point of Sale',
    'version':'0.0.1',
    'website':'https://globalresponse.cl',
    'author':'Daniel Santibáñez Polanco',
    'license': 'AGPL-3',
    'data': [
        'views/pos_config.xml',
    ],
    'depends': [
        'point_of_sale',
    ],'assets': {
        'point_of_sale.assets': [
            "pos_xml_receipt/static/src/js/printers.js",
            "pos_xml_receipt/static/src/js/AbstractReceiptScreen.js",
            'pos_xml_receipt/static/src/xml/**/*',
        ],
    },
    'application': True,
}
