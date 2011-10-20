#! /usr/bin/env python

# Copyright (c) 2008, PediaPress GmbH
# See README.rst for additional licensing information.

class OdfConf(object):
        paper = {
                        'PAPER_WIDTH' : 8.3,
                        'PAPER_HEIGHT' : 11.7,
                        'MAX_IMG_COVER_FACTOR' : 0.4, #[%] 0.4 = the image covers max 40% of the page
                        'PAGE_BORDER_TOP' : 0.8,      #[inch] spaces between paper-border and printable area
                        'PAGE_BORDER_BOTTOM' : 0.8,   #[inch] spaces between paper-border and printable area
                        'PAGE_BORDER_LEFT' : 0.8,     #[inch] spaces between paper-border and printable area
                        'PAGE_BORDER_RIGHT' : 0.8,    #[inch] spaces between paper-border and printable area
                        'IMG_DPI_STANDARD' : 96,      #[dpi] means a image with 120px, needs 120[px]/96[dpi] =  1,25[in] inces on DIN A4
                        'IMG_DPI_INLINE' : 96,       #[dpi] see above
                        }
        paper['IMG_MAX_WIDTH'] = paper['MAX_IMG_COVER_FACTOR'] * \
            (paper['PAPER_WIDTH'] - paper['PAGE_BORDER_LEFT'] - paper['PAGE_BORDER_RIGHT'])
        paper['IMG_MAX_HEIGHT'] = paper['MAX_IMG_COVER_FACTOR'] * \
            (paper['PAPER_HEIGHT'] - paper['PAGE_BORDER_TOP'] - paper['PAGE_BORDER_BOTTOM'])
        

# Config paper size  (in INCH)
#
# 1pt = 1/72in, see  http://en.wikipedia.org/wiki/Point_(typography)#Current_DTP_point_system
# Constants (all values in inch!)

#inline_img_dpi = 100 # scaling factor for inline images. 100 dpi should be the ideal size in relation to 10pt text size 
#????
#targetWidth = 800  # target image width 
#scale = 1./75
