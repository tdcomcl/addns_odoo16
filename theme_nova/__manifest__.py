{
    "name": "Theme Nova",
    "version": "16.0.1.0",
    'author': "Bytesfuel",
    'website': "https://bytesfuel.com/",
    "depends": ['website','website_crm'],
    "category": "Theme",
    'data': [
        'views/footer_template.xml',
        'views/snippets.xml',
     ],
    'assets': {
        'web.assets_frontend': [
            '/theme_nova/static/src/scss/theme.scss',
            '/theme_nova/static/src/js/main.js',
        ],

        'web._assets_primary_variables': [
            '/theme_nova/static/src/scss/primary_variables.scss',

        ],
    },
    'images': [
        'static/description/theme_banner.png',
        'static/description/theme_screenshot.png',
    ],
   'license': 'AGPL-3',
    'application': False,
    'license': 'OPL-1',
}
