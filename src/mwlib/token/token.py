class Token:
    t_end = 0
    t_text = 1
    t_entity = 2
    t_special = 3
    t_magicword = 4
    t_comment = 5
    t_2box_open = 6
    t_2box_close = 7
    t_http_url = 8
    t_break = 9
    t_begin_table = 10
    t_end_table = 11
    t_html_tag = 12
    t_singlequote = 13
    t_pre = 14
    t_section = 15
    t_section_end = 16
    t_item = 17
    t_colon = 18
    t_semicolon = 19
    t_hrule = 20
    t_newline = 21
    t_column = 22
    t_row = 23
    t_tablecaption = 24
    t_urllink = 25
    t_uniq = 26

    t_html_tag_end = 100
    token2name = {}
