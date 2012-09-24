import locale

_supported = ['aa_DJ', 'aa_DJ.UTF-8', 'aa_ER', 'aa_ER@saaho', 'aa_ET',
'af_ZA', 'af_ZA.UTF-8', 'am_ET', 'an_ES', 'an_ES.UTF-8', 'ar_AE',
'ar_AE.UTF-8', 'ar_BH', 'ar_BH.UTF-8', 'ar_DZ', 'ar_DZ.UTF-8',
'ar_EG', 'ar_EG.UTF-8', 'ar_IN', 'ar_IQ', 'ar_IQ.UTF-8', 'ar_JO',
'ar_JO.UTF-8', 'ar_KW', 'ar_KW.UTF-8', 'ar_LB', 'ar_LB.UTF-8',
'ar_LY', 'ar_LY.UTF-8', 'ar_MA', 'ar_MA.UTF-8', 'ar_OM',
'ar_OM.UTF-8', 'ar_QA', 'ar_QA.UTF-8', 'ar_SA', 'ar_SA.UTF-8',
'ar_SD', 'ar_SD.UTF-8', 'ar_SY', 'ar_SY.UTF-8', 'ar_TN',
'ar_TN.UTF-8', 'ar_YE', 'ar_YE.UTF-8', 'as_IN', 'ast_ES',
'ast_ES.UTF-8', 'az_AZ', 'be_BY', 'be_BY.UTF-8', 'be_BY@latin',
'bem_ZM', 'ber_DZ', 'ber_MA', 'bg_BG', 'bg_BG.UTF-8', 'bho_IN',
'bn_BD', 'bn_IN', 'bo_CN', 'bo_IN', 'br_FR', 'br_FR.UTF-8',
'br_FR@euro', 'brx_IN', 'bs_BA', 'bs_BA.UTF-8', 'byn_ER', 'ca_AD',
'ca_AD.UTF-8', 'ca_ES', 'ca_ES.UTF-8', 'ca_ES@euro', 'ca_FR',
'ca_FR.UTF-8', 'ca_IT', 'ca_IT.UTF-8', 'crh_UA', 'cs_CZ',
'cs_CZ.UTF-8', 'csb_PL', 'cv_RU', 'cy_GB', 'cy_GB.UTF-8', 'da_DK',
'da_DK.UTF-8', 'de_AT', 'de_AT.UTF-8', 'de_AT@euro', 'de_BE',
'de_BE.UTF-8', 'de_BE@euro', 'de_CH', 'de_CH.UTF-8', 'de_DE',
'de_DE.UTF-8', 'de_DE@euro', 'de_LU', 'de_LU.UTF-8', 'de_LU@euro',
'dv_MV', 'dz_BT', 'el_CY', 'el_CY.UTF-8', 'el_GR', 'el_GR.UTF-8',
'en_AG', 'en_AU', 'en_AU.UTF-8', 'en_BW', 'en_BW.UTF-8', 'en_CA',
'en_CA.UTF-8', 'en_DK', 'en_DK.UTF-8', 'en_GB', 'en_GB.UTF-8',
'en_HK', 'en_HK.UTF-8', 'en_IE', 'en_IE.UTF-8', 'en_IE@euro', 'en_IN',
'en_NG', 'en_NZ', 'en_NZ.UTF-8', 'en_PH', 'en_PH.UTF-8', 'en_SG',
'en_SG.UTF-8', 'en_US', 'en_US.UTF-8', 'en_ZA', 'en_ZA.UTF-8',
'en_ZM', 'en_ZW', 'en_ZW.UTF-8', 'es_AR', 'es_AR.UTF-8', 'es_BO',
'es_BO.UTF-8', 'es_CL', 'es_CL.UTF-8', 'es_CO', 'es_CO.UTF-8',
'es_CR', 'es_CR.UTF-8', 'es_CU', 'es_DO', 'es_DO.UTF-8', 'es_EC',
'es_EC.UTF-8', 'es_ES', 'es_ES.UTF-8', 'es_ES@euro', 'es_GT',
'es_GT.UTF-8', 'es_HN', 'es_HN.UTF-8', 'es_MX', 'es_MX.UTF-8',
'es_NI', 'es_NI.UTF-8', 'es_PA', 'es_PA.UTF-8', 'es_PE',
'es_PE.UTF-8', 'es_PR', 'es_PR.UTF-8', 'es_PY', 'es_PY.UTF-8',
'es_SV', 'es_SV.UTF-8', 'es_US', 'es_US.UTF-8', 'es_UY',
'es_UY.UTF-8', 'es_VE', 'es_VE.UTF-8', 'et_EE', 'et_EE.ISO-8859-15',
'et_EE.UTF-8', 'eu_ES', 'eu_ES.UTF-8', 'eu_ES@euro', 'fa_IR', 'ff_SN',
'fi_FI', 'fi_FI.UTF-8', 'fi_FI@euro', 'fil_PH', 'fo_FO',
'fo_FO.UTF-8', 'fr_BE', 'fr_BE.UTF-8', 'fr_BE@euro', 'fr_CA',
'fr_CA.UTF-8', 'fr_CH', 'fr_CH.UTF-8', 'fr_FR', 'fr_FR.UTF-8',
'fr_FR@euro', 'fr_LU', 'fr_LU.UTF-8', 'fr_LU@euro', 'fur_IT', 'fy_DE',
'fy_NL', 'ga_IE', 'ga_IE.UTF-8', 'ga_IE@euro', 'gd_GB', 'gd_GB.UTF-8',
'gez_ER', 'gez_ER@abegede', 'gez_ET', 'gez_ET@abegede', 'gl_ES',
'gl_ES.UTF-8', 'gl_ES@euro', 'gu_IN', 'gv_GB', 'gv_GB.UTF-8', 'ha_NG',
'he_IL', 'he_IL.UTF-8', 'hi_IN', 'hne_IN', 'hr_HR', 'hr_HR.UTF-8',
'hsb_DE', 'hsb_DE.UTF-8', 'ht_HT', 'hu_HU', 'hu_HU.UTF-8', 'hy_AM',
'hy_AM.ARMSCII-8', 'id_ID', 'id_ID.UTF-8', 'ig_NG', 'ik_CA', 'is_IS',
'is_IS.UTF-8', 'it_CH', 'it_CH.UTF-8', 'it_IT', 'it_IT.UTF-8',
'it_IT@euro', 'iu_CA', 'iw_IL', 'iw_IL.UTF-8', 'ja_JP.EUC-JP',
'ja_JP.UTF-8', 'ka_GE', 'ka_GE.UTF-8', 'kk_KZ', 'kk_KZ.UTF-8',
'kl_GL', 'kl_GL.UTF-8', 'km_KH', 'kn_IN', 'ko_KR.EUC-KR',
'ko_KR.UTF-8', 'kok_IN', 'ks_IN', 'ks_IN@devanagari', 'ku_TR',
'ku_TR.UTF-8', 'kw_GB', 'kw_GB.UTF-8', 'ky_KG', 'lb_LU', 'lg_UG',
'lg_UG.UTF-8', 'li_BE', 'li_NL', 'lij_IT', 'lo_LA', 'lt_LT',
'lt_LT.UTF-8', 'lv_LV', 'lv_LV.UTF-8', 'mai_IN', 'mg_MG',
'mg_MG.UTF-8', 'mhr_RU', 'mi_NZ', 'mi_NZ.UTF-8', 'mk_MK',
'mk_MK.UTF-8', 'ml_IN', 'mn_MN', 'mr_IN', 'ms_MY', 'ms_MY.UTF-8',
'mt_MT', 'mt_MT.UTF-8', 'my_MM', 'nan_TW@latin', 'nb_NO',
'nb_NO.UTF-8', 'nds_DE', 'nds_NL', 'ne_NP', 'nl_AW', 'nl_BE',
'nl_BE.UTF-8', 'nl_BE@euro', 'nl_NL', 'nl_NL.UTF-8', 'nl_NL@euro',
'nn_NO', 'nn_NO.UTF-8', 'nr_ZA', 'nso_ZA', 'oc_FR', 'oc_FR.UTF-8',
'om_ET', 'om_KE', 'om_KE.UTF-8', 'or_IN', 'os_RU', 'pa_IN', 'pa_PK',
'pap_AN', 'pl_PL', 'pl_PL.UTF-8', 'ps_AF', 'pt_BR', 'pt_BR.UTF-8',
'pt_PT', 'pt_PT.UTF-8', 'pt_PT@euro', 'ro_RO', 'ro_RO.UTF-8', 'ru_RU',
'ru_RU.KOI8-R', 'ru_RU.UTF-8', 'ru_UA', 'ru_UA.UTF-8', 'rw_RW',
'sa_IN', 'sc_IT', 'sd_IN', 'sd_IN@devanagari', 'se_NO', 'shs_CA',
'si_LK', 'sid_ET', 'sk_SK', 'sk_SK.UTF-8', 'sl_SI', 'sl_SI.UTF-8',
'so_DJ', 'so_DJ.UTF-8', 'so_ET', 'so_KE', 'so_KE.UTF-8', 'so_SO',
'so_SO.UTF-8', 'sq_AL', 'sq_AL.UTF-8', 'sq_MK', 'sr_ME', 'sr_RS',
'sr_RS@latin', 'ss_ZA', 'st_ZA', 'st_ZA.UTF-8', 'sv_FI',
'sv_FI.UTF-8', 'sv_FI@euro', 'sv_SE', 'sv_SE.UTF-8', 'sw_KE', 'sw_TZ',
'ta_IN', 'ta_LK', 'te_IN', 'tg_TJ', 'tg_TJ.UTF-8', 'th_TH',
'th_TH.UTF-8', 'ti_ER', 'ti_ET', 'tig_ER', 'tk_TM', 'tl_PH',
'tl_PH.UTF-8', 'tn_ZA', 'tr_CY', 'tr_CY.UTF-8', 'tr_TR',
'tr_TR.UTF-8', 'ts_ZA', 'tt_RU', 'tt_RU@iqtelif', 'ug_CN', 'uk_UA',
'uk_UA.UTF-8', 'unm_US', 'ur_IN', 'ur_PK', 'uz_UZ', 'uz_UZ@cyrillic',
've_ZA', 'vi_VN', 'vi_VN.TCVN', 'wa_BE', 'wa_BE.UTF-8', 'wa_BE@euro',
'wae_CH', 'wal_ET', 'wo_SN', 'xh_ZA', 'xh_ZA.UTF-8', 'yi_US',
'yi_US.UTF-8', 'yo_NG', 'yue_HK', 'zh_CN', 'zh_CN.GB18030',
'zh_CN.GBK', 'zh_CN.UTF-8', 'zh_HK', 'zh_HK.UTF-8', 'zh_SG',
'zh_SG.GBK', 'zh_SG.UTF-8', 'zh_TW', 'zh_TW.EUC-TW', 'zh_TW.UTF-8',
'zu_ZA', 'zu_ZA.UTF-8']

lang2locale = {
    "de": ("de_DE.UTF-8", "de_DE"),
    "en": ("en_US.UTF-8",)}

current_lang = None


def set_locale_from_lang(lang):
    global current_lang

    if lang == current_lang:
        return

    prefix = lang + u"_"

    tried = []
    for x in ["%s_%s" % (lang, lang.upper())] + _supported:
        if x.startswith(prefix):
            try:
                locale.setlocale(locale.LC_NUMERIC, x)
                current_lang = lang
                print "set locale to %r based on the language %r" % (x, current_lang)
                return
            except locale.Error:
                tried.append(x)

    print "failed to set locale for language %r, tried %r" % (lang, tried)
