# modules/esad_address.py
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import json
from datetime import datetime
import requests
import os
try:
    from config import OPENROUTER_API_KEY, OPENROUTER_GENERAL_MODELS
except ImportError:
    from customs_api.config import OPENROUTER_API_KEY, OPENROUTER_GENERAL_MODELS

# Comprehensive country code mappings
ISO2_TO_COUNTRY = {
    'AD': 'Andorra', 'AE': 'United Arab Emirates', 'AF': 'Afghanistan', 'AG': 'Antigua and Barbuda',
    'AI': 'Anguilla', 'AL': 'Albania', 'AM': 'Armenia', 'AO': 'Angola', 'AQ': 'Antarctica',
    'AR': 'Argentina', 'AS': 'American Samoa', 'AT': 'Austria', 'AU': 'Australia', 'AW': 'Aruba',
    'AX': 'Åland Islands', 'AZ': 'Azerbaijan', 'BA': 'Bosnia and Herzegovina', 'BB': 'Barbados',
    'BD': 'Bangladesh', 'BE': 'Belgium', 'BF': 'Burkina Faso', 'BG': 'Bulgaria', 'BH': 'Bahrain',
    'BI': 'Burundi', 'BJ': 'Benin', 'BL': 'Saint Barthélemy', 'BM': 'Bermuda', 'BN': 'Brunei',
    'BO': 'Bolivia', 'BQ': 'Caribbean Netherlands', 'BR': 'Brazil', 'BS': 'Bahamas', 'BT': 'Bhutan',
    'BV': 'Bouvet Island', 'BW': 'Botswana', 'BY': 'Belarus', 'BZ': 'Belize', 'CA': 'Canada',
    'CC': 'Cocos Islands', 'CD': 'Democratic Republic of the Congo', 'CF': 'Central African Republic',
    'CG': 'Republic of the Congo', 'CH': 'Switzerland', 'CI': 'Côte d\'Ivoire', 'CK': 'Cook Islands',
    'CL': 'Chile', 'CM': 'Cameroon', 'CN': 'China', 'CO': 'Colombia', 'CR': 'Costa Rica',
    'CU': 'Cuba', 'CV': 'Cape Verde', 'CW': 'Curaçao', 'CX': 'Christmas Island', 'CY': 'Cyprus',
    'CZ': 'Czech Republic', 'DE': 'Germany', 'DJ': 'Djibouti', 'DK': 'Denmark', 'DM': 'Dominica',
    'DO': 'Dominican Republic', 'DZ': 'Algeria', 'EC': 'Ecuador', 'EE': 'Estonia', 'EG': 'Egypt',
    'EH': 'Western Sahara', 'ER': 'Eritrea', 'ES': 'Spain', 'ET': 'Ethiopia', 'FI': 'Finland',
    'FJ': 'Fiji', 'FK': 'Falkland Islands', 'FM': 'Micronesia', 'FO': 'Faroe Islands', 'FR': 'France',
    'GA': 'Gabon', 'GB': 'United Kingdom', 'GD': 'Grenada', 'GE': 'Georgia', 'GF': 'French Guiana',
    'GG': 'Guernsey', 'GH': 'Ghana', 'GI': 'Gibraltar', 'GL': 'Greenland', 'GM': 'Gambia',
    'GN': 'Guinea', 'GP': 'Guadeloupe', 'GQ': 'Equatorial Guinea', 'GR': 'Greece', 'GS': 'South Georgia',
    'GT': 'Guatemala', 'GU': 'Guam', 'GW': 'Guinea-Bissau', 'GY': 'Guyana', 'HK': 'Hong Kong',
    'HM': 'Heard Island', 'HN': 'Honduras', 'HR': 'Croatia', 'HT': 'Haiti', 'HU': 'Hungary',
    'ID': 'Indonesia', 'IE': 'Ireland', 'IL': 'Israel', 'IM': 'Isle of Man', 'IN': 'India',
    'IO': 'British Indian Ocean Territory', 'IQ': 'Iraq', 'IR': 'Iran', 'IS': 'Iceland',
    'IT': 'Italy', 'JE': 'Jersey', 'JM': 'Jamaica', 'JO': 'Jordan', 'JP': 'Japan',
    'KE': 'Kenya', 'KG': 'Kyrgyzstan', 'KH': 'Cambodia', 'KI': 'Kiribati', 'KM': 'Comoros',
    'KN': 'Saint Kitts and Nevis', 'KP': 'North Korea', 'KR': 'South Korea', 'KW': 'Kuwait',
    'KY': 'Cayman Islands', 'KZ': 'Kazakhstan', 'LA': 'Laos', 'LB': 'Lebanon', 'LC': 'Saint Lucia',
    'LI': 'Liechtenstein', 'LK': 'Sri Lanka', 'LR': 'Liberia', 'LS': 'Lesotho', 'LT': 'Lithuania',
    'LU': 'Luxembourg', 'LV': 'Latvia', 'LY': 'Libya', 'MA': 'Morocco', 'MC': 'Monaco',
    'MD': 'Moldova', 'ME': 'Montenegro', 'MF': 'Saint Martin', 'MG': 'Madagascar', 'MH': 'Marshall Islands',
    'MK': 'North Macedonia', 'ML': 'Mali', 'MM': 'Myanmar', 'MN': 'Mongolia', 'MO': 'Macao',
    'MP': 'Northern Mariana Islands', 'MQ': 'Martinique', 'MR': 'Mauritania', 'MS': 'Montserrat',
    'MT': 'Malta', 'MU': 'Mauritius', 'MV': 'Maldives', 'MW': 'Malawi', 'MX': 'Mexico',
    'MY': 'Malaysia', 'MZ': 'Mozambique', 'NA': 'Namibia', 'NC': 'New Caledonia', 'NE': 'Niger',
    'NF': 'Norfolk Island', 'NG': 'Nigeria', 'NI': 'Nicaragua', 'NL': 'Netherlands', 'NO': 'Norway',
    'NP': 'Nepal', 'NR': 'Nauru', 'NU': 'Niue', 'NZ': 'New Zealand', 'OM': 'Oman',
    'PA': 'Panama', 'PE': 'Peru', 'PF': 'French Polynesia', 'PG': 'Papua New Guinea', 'PH': 'Philippines',
    'PK': 'Pakistan', 'PL': 'Poland', 'PM': 'Saint Pierre and Miquelon', 'PN': 'Pitcairn Islands',
    'PR': 'Puerto Rico', 'PS': 'Palestine', 'PT': 'Portugal', 'PW': 'Palau', 'PY': 'Paraguay',
    'QA': 'Qatar', 'RE': 'Réunion', 'RO': 'Romania', 'RS': 'Serbia', 'RU': 'Russia',
    'RW': 'Rwanda', 'SA': 'Saudi Arabia', 'SB': 'Solomon Islands', 'SC': 'Seychelles', 'SD': 'Sudan',
    'SE': 'Sweden', 'SG': 'Singapore', 'SH': 'Saint Helena', 'SI': 'Slovenia', 'SJ': 'Svalbard',
    'SK': 'Slovakia', 'SL': 'Sierra Leone', 'SM': 'San Marino', 'SN': 'Senegal', 'SO': 'Somalia',
    'SR': 'Suriname', 'SS': 'South Sudan', 'ST': 'São Tomé and Príncipe', 'SV': 'El Salvador',
    'SX': 'Sint Maarten', 'SY': 'Syria', 'SZ': 'Eswatini', 'TC': 'Turks and Caicos Islands',
    'TD': 'Chad', 'TF': 'French Southern Territories', 'TG': 'Togo', 'TH': 'Thailand',
    'TJ': 'Tajikistan', 'TK': 'Tokelau', 'TL': 'East Timor', 'TM': 'Turkmenistan', 'TN': 'Tunisia',
    'TO': 'Tonga', 'TR': 'Turkey', 'TT': 'Trinidad and Tobago', 'TV': 'Tuvalu', 'TW': 'Taiwan',
    'TZ': 'Tanzania', 'UA': 'Ukraine', 'UG': 'Uganda', 'UM': 'United States Minor Outlying Islands',
    'US': 'United States', 'UY': 'Uruguay', 'UZ': 'Uzbekistan', 'VA': 'Vatican City',
    'VC': 'Saint Vincent and the Grenadines', 'VE': 'Venezuela', 'VG': 'British Virgin Islands',
    'VI': 'United States Virgin Islands', 'VN': 'Vietnam', 'VU': 'Vanuatu', 'WF': 'Wallis and Futuna',
    'WS': 'Samoa', 'YE': 'Yemen', 'YT': 'Mayotte', 'ZA': 'South Africa', 'ZM': 'Zambia', 'ZW': 'Zimbabwe'
}

# Major airport codes to country mapping
AIRPORT_TO_COUNTRY = {
    'MIA': 'United States', 'JFK': 'United States', 'LAX': 'United States', 'ORD': 'United States',
    'DFW': 'United States', 'DEN': 'United States', 'ATL': 'United States', 'SEA': 'United States',
    'LAS': 'United States', 'PHX': 'United States', 'IAH': 'United States', 'MCO': 'United States',
    'BOS': 'United States', 'DTW': 'United States', 'MSP': 'United States', 'EWR': 'United States',
    'SFO': 'United States', 'CLT': 'United States', 'PHL': 'United States', 'LGA': 'United States',
    'BWI': 'United States', 'DCA': 'United States', 'IAD': 'United States', 'FLL': 'United States',
    'TPA': 'United States', 'MCI': 'United States', 'STL': 'United States', 'PDX': 'United States',
    'SAN': 'United States', 'AUS': 'United States', 'BNA': 'United States', 'MSY': 'United States',
    'SLC': 'United States', 'HNL': 'United States', 'KIN': 'Jamaica', 'NMIA': 'Jamaica',
    'HKG': 'Hong Kong', 'PEK': 'China', 'PVG': 'China', 'CAN': 'China', 'SZX': 'China',
    'NRT': 'Japan', 'HND': 'Japan', 'KIX': 'Japan', 'ICN': 'South Korea', 'GMP': 'South Korea',
    'SIN': 'Singapore', 'KUL': 'Malaysia', 'BKK': 'Thailand', 'DMK': 'Thailand',
    'MNL': 'Philippines', 'CGK': 'Indonesia', 'DPS': 'Indonesia', 'BOM': 'India',
    'DEL': 'India', 'BLR': 'India', 'MAA': 'India', 'CCU': 'India', 'HYD': 'India',
    'DXB': 'United Arab Emirates', 'AUH': 'United Arab Emirates', 'DOH': 'Qatar',
    'KWI': 'Kuwait', 'BAH': 'Bahrain', 'RUH': 'Saudi Arabia', 'JED': 'Saudi Arabia',
    'IST': 'Turkey', 'SAW': 'Turkey', 'TLV': 'Israel', 'CAI': 'Egypt', 'JNB': 'South Africa',
    'CPT': 'South Africa', 'DUR': 'South Africa', 'LHR': 'United Kingdom', 'LGW': 'United Kingdom',
    'STN': 'United Kingdom', 'MAN': 'United Kingdom', 'BHX': 'United Kingdom', 'GLA': 'United Kingdom',
    'EDI': 'United Kingdom', 'BFS': 'United Kingdom', 'CDG': 'France', 'ORY': 'France',
    'LYS': 'France', 'MRS': 'France', 'NCE': 'France', 'TLS': 'France', 'BOD': 'France',
    'FRA': 'Germany', 'MUC': 'Germany', 'DUS': 'Germany', 'HAM': 'Germany', 'CGN': 'Germany',
    'STR': 'Germany', 'LEJ': 'Germany', 'FCO': 'Italy', 'MXP': 'Italy', 'LIN': 'Italy',
    'VCE': 'Italy', 'NAP': 'Italy', 'BGO': 'Italy', 'MAD': 'Spain', 'BCN': 'Spain',
    'VLC': 'Spain', 'SVQ': 'Spain', 'BIO': 'Spain', 'AGP': 'Spain', 'LIS': 'Portugal',
    'OPO': 'Portugal', 'AMS': 'Netherlands', 'EIN': 'Netherlands', 'RTM': 'Netherlands',
    'BRU': 'Belgium', 'CRL': 'Belgium', 'VIE': 'Austria', 'ZUR': 'Switzerland', 'GVA': 'Switzerland',
    'ARN': 'Sweden', 'GOT': 'Sweden', 'CPH': 'Denmark', 'OSL': 'Norway', 'HEL': 'Finland',
    'WAW': 'Poland', 'KRK': 'Poland', 'PRG': 'Czech Republic', 'BUD': 'Hungary',
    'OTP': 'Romania', 'SOF': 'Bulgaria', 'ATH': 'Greece', 'SKG': 'Greece',
    'DUB': 'Ireland', 'SNN': 'Ireland', 'KEF': 'Iceland', 'REK': 'Iceland',
    'YUL': 'Canada', 'YYZ': 'Canada', 'YVR': 'Canada', 'YYC': 'Canada', 'YEG': 'Canada',
    'YWG': 'Canada', 'YHZ': 'Canada', 'YOW': 'Canada', 'YQB': 'Canada', 'YQR': 'Canada',
    'GRU': 'Brazil', 'GIG': 'Brazil', 'BSB': 'Brazil', 'CGH': 'Brazil', 'CNF': 'Brazil',
    'EZE': 'Argentina', 'AEP': 'Argentina', 'COR': 'Argentina', 'MDZ': 'Argentina',
    'SCL': 'Chile', 'LIM': 'Peru', 'BOG': 'Colombia', 'UIO': 'Ecuador', 'ASU': 'Paraguay',
    'MVD': 'Uruguay', 'CCS': 'Venezuela', 'PTY': 'Panama', 'SJO': 'Costa Rica',
    'GUA': 'Guatemala', 'SAP': 'Honduras', 'SAL': 'El Salvador', 'MGA': 'Nicaragua',
    'TGU': 'Honduras', 'BZE': 'Belize', 'CUN': 'Mexico', 'MEX': 'Mexico', 'GDL': 'Mexico',
    'MTY': 'Mexico', 'TIJ': 'Mexico', 'PVR': 'Mexico', 'CZM': 'Mexico', 'ACA': 'Mexico',
    'HAV': 'Cuba', 'SNU': 'Cuba', 'VRA': 'Cuba', 'SDQ': 'Dominican Republic', 'PUJ': 'Dominican Republic',
    'STI': 'Dominican Republic', 'POP': 'Dominican Republic', 'SJU': 'Puerto Rico',
    'BGI': 'Barbados', 'POS': 'Trinidad and Tobago', 'GND': 'Grenada', 'SLU': 'Saint Lucia',
    'ANU': 'Antigua and Barbuda', 'SKB': 'Saint Kitts and Nevis', 'SVD': 'Saint Vincent and the Grenadines',
    'DOM': 'Dominica', 'TAB': 'Tobago', 'PLS': 'Turks and Caicos Islands', 'NAS': 'Bahamas',
    'FPO': 'Bahamas', 'GCM': 'Cayman Islands', 'UVF': 'Saint Lucia', 'BDA': 'Bermuda',
    'SXM': 'Sint Maarten', 'AXA': 'Anguilla', 'EIS': 'British Virgin Islands', 'VIJ': 'British Virgin Islands',
    'STT': 'United States Virgin Islands', 'STX': 'United States Virgin Islands'
}

# Major seaport codes to country mapping  
SEAPORT_TO_COUNTRY = {
    'LAX': 'United States', 'LGB': 'United States', 'OAK': 'United States', 'SEA': 'United States',
    'NYC': 'United States', 'BAL': 'United States', 'NOR': 'United States', 'SAV': 'United States',
    'CHA': 'United States', 'MOB': 'United States', 'HOU': 'United States', 'GAL': 'United States',
    'COR': 'United States', 'POR': 'United States', 'BOS': 'United States', 'PHI': 'United States',
    'JAX': 'United States', 'TAM': 'United States', 'KIN': 'Jamaica',
    'HKG': 'Hong Kong', 'SHA': 'China', 'TSN': 'China', 'QIN': 'China', 'DAL': 'China',
    'NGB': 'China', 'FOC': 'China', 'XMN': 'China', 'ZHA': 'China', 'YAN': 'China',
    'YOK': 'Japan', 'OSA': 'Japan', 'NAG': 'Japan', 'KOB': 'Japan', 'HAK': 'Japan',
    'BUS': 'South Korea', 'INC': 'South Korea', 'PUS': 'South Korea', 'ULS': 'South Korea',
    'SIN': 'Singapore', 'KUL': 'Malaysia', 'PEN': 'Malaysia', 'JOH': 'Malaysia',
    'BKK': 'Thailand', 'LCH': 'Thailand', 'SON': 'Thailand', 'SAT': 'Thailand',
    'MNL': 'Philippines', 'CEB': 'Philippines', 'DVO': 'Philippines', 'ILO': 'Philippines',
    'JKT': 'Indonesia', 'SBY': 'Indonesia', 'MDN': 'Indonesia', 'PLM': 'Indonesia',
    'BOM': 'India', 'CAL': 'India', 'MAA': 'India', 'COC': 'India', 'VIZ': 'India',
    'CCU': 'India', 'KAN': 'India', 'PAR': 'India', 'GOA': 'India',
    'DXB': 'United Arab Emirates', 'AUH': 'United Arab Emirates', 'SHJ': 'United Arab Emirates',
    'DOH': 'Qatar', 'KWI': 'Kuwait', 'BAH': 'Bahrain', 'RUH': 'Saudi Arabia',
    'JED': 'Saudi Arabia', 'DAM': 'Saudi Arabia', 'IST': 'Turkey', 'IZM': 'Turkey',
    'MER': 'Turkey', 'SAM': 'Turkey', 'TLV': 'Israel', 'HAI': 'Israel', 'ASH': 'Israel',
    'CAI': 'Egypt', 'ALE': 'Egypt', 'POR': 'Egypt', 'SUE': 'Egypt',
    'JNB': 'South Africa', 'CPT': 'South Africa', 'DUR': 'South Africa', 'PLZ': 'South Africa',
    'LON': 'United Kingdom', 'LIV': 'United Kingdom', 'MAN': 'United Kingdom', 'BIR': 'United Kingdom',
    'GLA': 'United Kingdom', 'EDI': 'United Kingdom', 'BEL': 'United Kingdom', 'CAR': 'United Kingdom',
    'PAR': 'France', 'MAR': 'France', 'LYO': 'France', 'NIC': 'France', 'BOR': 'France',
    'LEH': 'France', 'TOU': 'France', 'HAR': 'France', 'DUN': 'France', 'CAL': 'France',
    'HAM': 'Germany', 'BRE': 'Germany', 'KIE': 'Germany', 'LUE': 'Germany',
    'ROS': 'Germany', 'EMD': 'Germany', 'DUI': 'Germany', 'KOB': 'Germany', 'BRA': 'Germany',
    'ROM': 'Italy', 'MIL': 'Italy', 'GEN': 'Italy', 'VEN': 'Italy', 'NAP': 'Italy',
    'BOL': 'Italy', 'TAR': 'Italy', 'MES': 'Italy', 'CAG': 'Italy', 'PAL': 'Italy',
    'MAD': 'Spain', 'BAR': 'Spain', 'VAL': 'Spain', 'SEV': 'Spain', 'BIL': 'Spain',
    'COR': 'Spain', 'VIG': 'Spain', 'ALG': 'Spain', 'CAD': 'Spain', 'SAN': 'Spain',
    'LIS': 'Portugal', 'OPO': 'Portugal', 'SET': 'Portugal', 'AVE': 'Portugal', 'FAR': 'Portugal',
    'AMS': 'Netherlands', 'ROT': 'Netherlands', 'EIN': 'Netherlands', 'GRO': 'Netherlands',
    'BRU': 'Belgium', 'ANT': 'Belgium', 'GHE': 'Belgium', 'ZEE': 'Belgium', 'OST': 'Belgium',
    'VIE': 'Austria', 'GRA': 'Austria', 'LIN': 'Austria', 'SAL': 'Austria', 'KLG': 'Austria',
    'ZUR': 'Switzerland', 'BAS': 'Switzerland', 'BER': 'Switzerland', 'GEN': 'Switzerland',
    'STO': 'Sweden', 'GOT': 'Sweden', 'MAL': 'Sweden', 'NOR': 'Sweden', 'HEL': 'Sweden',
    'COP': 'Denmark', 'AAR': 'Denmark', 'ODS': 'Denmark', 'AAL': 'Denmark', 'ESB': 'Denmark',
    'OSL': 'Norway', 'BER': 'Norway', 'TRO': 'Norway', 'STA': 'Norway', 'KRI': 'Norway',
    'HEL': 'Finland', 'TUR': 'Finland', 'TAM': 'Finland', 'POR': 'Finland', 'KOT': 'Finland',
    'WAR': 'Poland', 'GDA': 'Poland', 'SZC': 'Poland', 'WRO': 'Poland', 'POZ': 'Poland',
    'PRA': 'Czech Republic', 'OST': 'Czech Republic', 'BRN': 'Czech Republic', 'PLZ': 'Czech Republic',
    'BUD': 'Hungary', 'DEB': 'Hungary', 'SZE': 'Hungary', 'PEC': 'Hungary', 'GYO': 'Hungary',
    'BUC': 'Romania', 'CON': 'Romania', 'GAL': 'Romania', 'BRA': 'Romania', 'TIM': 'Romania',
    'SOF': 'Bulgaria', 'VAR': 'Bulgaria', 'BUR': 'Bulgaria', 'RUS': 'Bulgaria', 'PLE': 'Bulgaria',
    'ATH': 'Greece', 'THE': 'Greece', 'VOL': 'Greece', 'PAT': 'Greece', 'HER': 'Greece',
    'DUB': 'Ireland', 'COR': 'Ireland', 'LIM': 'Ireland', 'GAL': 'Ireland', 'WAT': 'Ireland',
    'REK': 'Iceland', 'AKU': 'Iceland', 'ISF': 'Iceland', 'VES': 'Iceland', 'HOF': 'Iceland',
    'TOR': 'Canada', 'MON': 'Canada', 'VAN': 'Canada', 'CAL': 'Canada', 'EDM': 'Canada',
    'WIN': 'Canada', 'HAL': 'Canada', 'OTT': 'Canada', 'QUE': 'Canada', 'REG': 'Canada',
    'SAO': 'Brazil', 'RIO': 'Brazil', 'BRA': 'Brazil', 'CAM': 'Brazil', 'BEL': 'Brazil',
    'BUE': 'Argentina', 'COR': 'Argentina', 'MEN': 'Argentina', 'ROS': 'Argentina',
    'SAN': 'Chile', 'VAL': 'Chile', 'ANT': 'Chile', 'CON': 'Chile', 'TAL': 'Chile',
    'LIM': 'Peru', 'CAL': 'Peru', 'ARE': 'Peru', 'TAC': 'Peru', 'CHI': 'Peru',
    'BOG': 'Colombia', 'MED': 'Colombia', 'CAL': 'Colombia', 'BAR': 'Colombia', 'BUC': 'Colombia',
    'QUI': 'Ecuador', 'GUA': 'Ecuador', 'CUE': 'Ecuador', 'MAN': 'Ecuador', 'POR': 'Ecuador',
    'ASU': 'Paraguay', 'ENC': 'Paraguay', 'CDE': 'Paraguay', 'PED': 'Paraguay', 'VIL': 'Paraguay',
    'MON': 'Uruguay', 'PAY': 'Uruguay', 'COL': 'Uruguay', 'SAL': 'Uruguay', 'FRA': 'Uruguay',
    'CAR': 'Venezuela', 'MAR': 'Venezuela', 'VAL': 'Venezuela', 'BAR': 'Venezuela', 'CUM': 'Venezuela',
    'PAN': 'Panama', 'COL': 'Panama', 'BOC': 'Panama', 'DAV': 'Panama', 'CHI': 'Panama',
    'SAN': 'Costa Rica', 'LIM': 'Costa Rica', 'PUN': 'Costa Rica', 'CAR': 'Costa Rica', 'HER': 'Costa Rica',
    'GUA': 'Guatemala', 'QUE': 'Guatemala', 'ESC': 'Guatemala', 'RET': 'Guatemala', 'COB': 'Guatemala',
    'TEG': 'Honduras', 'SAN': 'Honduras', 'LA': 'Honduras', 'TOC': 'Honduras', 'CHO': 'Honduras',
    'SAN': 'El Salvador', 'MAN': 'Nicaragua', 'LEO': 'Nicaragua', 'GRA': 'Nicaragua', 'EST': 'Nicaragua', 'CHI': 'Nicaragua',
    'BEL': 'Belize', 'CAN': 'Mexico', 'MEX': 'Mexico', 'GUA': 'Mexico', 'MON': 'Mexico', 'TIJ': 'Mexico',
    'PUE': 'Mexico', 'MER': 'Mexico', 'LEO': 'Mexico', 'TOR': 'Mexico', 'HER': 'Mexico',
    'HAV': 'Cuba', 'SAN': 'Cuba', 'CAM': 'Cuba', 'BAY': 'Cuba', 'HOL': 'Cuba',
    'SAN': 'Dominican Republic', 'PUE': 'Dominican Republic', 'LA': 'Dominican Republic', 'ROM': 'Dominican Republic', 'HER': 'Dominican Republic',
    'SAN': 'Puerto Rico', 'PON': 'Puerto Rico', 'MAY': 'Puerto Rico', 'AGU': 'Puerto Rico', 'FAJ': 'Puerto Rico',
    'BRI': 'Barbados', 'POR': 'Trinidad and Tobago', 'SAN': 'Trinidad and Tobago', 'CHA': 'Trinidad and Tobago', 'COU': 'Trinidad and Tobago', 'SCA': 'Trinidad and Tobago',
    'SAI': 'Grenada', 'CAS': 'Saint Lucia', 'SAI': 'Antigua and Barbuda', 'BAS': 'Saint Kitts and Nevis',
    'KIN': 'Saint Vincent and the Grenadines', 'ROS': 'Dominica', 'SCA': 'Tobago',
    'PRO': 'Turks and Caicos Islands', 'NAS': 'Bahamas', 'FRE': 'Bahamas', 'GEO': 'Bahamas', 'EXU': 'Bahamas', 'ELE': 'Bahamas',
    'GEO': 'Cayman Islands', 'CAS': 'Saint Lucia', 'HAM': 'Bermuda', 'PHI': 'Sint Maarten',
    'ROA': 'Anguilla', 'ROA': 'British Virgin Islands', 'CHA': 'United States Virgin Islands'
}

def _infer_country_from_codes(text: str) -> Optional[str]:
    """Infer country from airport codes, seaport codes, or ISO codes in text."""
    if not text:
        return None
    
    text_upper = text.upper().strip()
    
    # Check ISO2 codes first
    if text_upper in ISO2_TO_COUNTRY:
        return ISO2_TO_COUNTRY[text_upper]
    
    # Check airport codes
    if text_upper in AIRPORT_TO_COUNTRY:
        return AIRPORT_TO_COUNTRY[text_upper]
    
    # Check seaport codes
    if text_upper in SEAPORT_TO_COUNTRY:
        return SEAPORT_TO_COUNTRY[text_upper]
    
    # Look for codes within text (e.g., "MIA" in "Miami International Airport")
    for code, country in AIRPORT_TO_COUNTRY.items():
        if code in text_upper:
            return country
    
    for code, country in SEAPORT_TO_COUNTRY.items():
        if code in text_upper:
            return country
    
    return None

def _infer_country_from_airports_ports(document: dict) -> Tuple[Optional[str], Optional[str]]:
    """Extract country information from airport/port data in the document."""
    consignor_country = None
    consignee_country = None
    
    # Check airport information
    airport_info = document.get('airport_info', {})
    if airport_info:
        # Check departure airport
        departure_code = airport_info.get('airport_of_departure_code')
        if departure_code:
            consignor_country = _infer_country_from_codes(departure_code)
        
        # Check destination airport
        destination_code = airport_info.get('airport_of_destination')
        if destination_code:
            consignee_country = _infer_country_from_codes(destination_code)
    
    # Check routing information
    routing = document.get('routing_and_destination', {})
    if routing:
        to_code = routing.get('TO')
        if to_code and not consignee_country:
            consignee_country = _infer_country_from_codes(to_code)
    
    # Check ports information
    ports = document.get('ports', {})
    if ports:
        origin = ports.get('origin')
        if origin and not consignor_country:
            consignor_country = _infer_country_from_codes(origin)
        
        destination = ports.get('routing_to')
        if destination and not consignee_country:
            consignee_country = _infer_country_from_codes(destination)
    
    # Check raw text snippets for airport/port codes
    raw_text = document.get('raw_visible_text_snippets', [])
    if raw_text:
        text_content = ' '.join(raw_text)
        if not consignor_country:
            consignor_country = _infer_country_from_codes(text_content)
        if not consignee_country:
            consignee_country = _infer_country_from_codes(text_content)
    
    return consignor_country, consignee_country

@dataclass
class AddressComponent:
    """Represents a component of an address"""
    street_town: str
    city: str
    state_province_parish: str
    country: str

@dataclass
class FormattedAddress:
    """Represents a formatted address"""
    original: str
    formatted: str
    components: AddressComponent
    confidence: float
    issues: List[str]

class AddressFormatter:
    """Enhanced address processor with consignor/consignee extraction capabilities"""
    
    def __init__(self):
        self.api_key = OPENROUTER_API_KEY
        # Use general models for secondary processing tasks
        self.primary_model = OPENROUTER_GENERAL_MODELS["kimi_standard"]
        self.backup_model = OPENROUTER_GENERAL_MODELS["kimi_standard"]
        
    def extract_consignor_consignee(self, document: dict) -> dict:
        """
        Using the preferred LLM model, extract consignor (shipper) and consignee
        name, street, city, and country from a shipping document (AWB/BOL).

        Returns a dict with keys: {"consignor": {"name": str|None, "street": str|None, "city": str|None, "country": str|None},
        "consignee": {"name": str|None, "street": str|None, "city": str|None, "country": str|None}}
        
        Note: Country is returned as full name (e.g., "Jamaica" not "JM")
        """
        import json as _json
        import requests as _requests

        def _extract_street(party: dict) -> str:
            """Extract street address from party data."""
            if not isinstance(party, dict):
                return ""
            street_parts = []
            # Look for street-specific fields
            for key in ('address_line1', 'address_line_1', 'street', 'street1', 'street_1'):
                val = party.get(key)
                if isinstance(val, str) and val.strip():
                    street_parts.append(val.strip())
            return ", ".join(street_parts) if street_parts else ""

        def _extract_city(party: dict) -> str:
            """Extract city from party data."""
            if not isinstance(party, dict):
                return ""
            # Look for city-specific fields
            for key in ('city', 'city_region', 'state', 'province', 'parish', 'region'):
                val = party.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()
            
            # Try to extract city from address_line2 if it looks like a city
            address_line2 = party.get('address_line2', '') or party.get('address_line_2', '')
            if address_line2 and isinstance(address_line2, str):
                # Look for common city indicators in address_line2
                city_indicators = ['TSUEN WAN', 'KINGSTON', 'MIAMI', 'HONG KONG', 'NEW YORK', 'LONDON']
                for indicator in city_indicators:
                    if indicator in address_line2.upper():
                        return indicator
                # If address_line2 doesn't contain numbers and looks like a city name
                if not any(char.isdigit() for char in address_line2) and len(address_line2.split()) <= 3:
                    return address_line2.strip()
            
            return ""
        
        def _combine_address_fields(party: dict) -> str:
            if not isinstance(party, dict):
                return ""
            parts = []
            # Support multiple common variants
            for key in (
                'address', 'address_line1', 'address_line_1', 'address_line2', 'address_line_2',
                'street', 'street1', 'street_1', 'street2', 'street_2',
                'city', 'city_region', 'state', 'province', 'parish', 'region',
                'postal_code', 'zip', 'country'
            ):
                val = party.get(key)
                if isinstance(val, str) and val.strip():
                    parts.append(val.strip())
            # De-duplicate while preserving order
            seen = set()
            unique_parts = []
            for p in parts:
                if p not in seen:
                    seen.add(p)
                    unique_parts.append(p)
            return ", ".join(unique_parts) if unique_parts else ""

        def _country_name_from_value(val: Optional[str]) -> Optional[str]:
            if not val:
                return None
            v = str(val).strip()
            
            # Use comprehensive country inference
            country = _infer_country_from_codes(v)
            if country:
                return country
            
            # If looks like a full country name already
            return v

        def _fallback_from_dict(doc: dict) -> dict:
            consignor = doc.get('shipper') or doc.get('consignor') or {}
            consignee = doc.get('consignee') or {}
            consignor_name = consignor.get('name') or None
            consignee_name = consignee.get('name') or None
            consignor_street = _extract_street(consignor) or None
            consignee_street = _extract_street(consignee) or None
            consignor_city = _extract_city(consignor) or None
            consignee_city = _extract_city(consignee) or None
            consignor_addr = _combine_address_fields(consignor) or None
            consignee_addr = _combine_address_fields(consignee) or None
            
            # Try direct country field first
            consignor_country = _country_name_from_value(consignor.get('country'))
            consignee_country = _country_name_from_value(consignee.get('country'))
            
            # If no country found, try airport/port inference
            if not consignor_country or not consignee_country:
                airport_consignor, airport_consignee = _infer_country_from_airports_ports(doc)
                if not consignor_country and airport_consignor:
                    consignor_country = airport_consignor
                if not consignee_country and airport_consignee:
                    consignee_country = airport_consignee
            
            # Convert ISO codes to full country names
            if consignor_country and len(consignor_country) == 2:
                consignor_country = ISO2_TO_COUNTRY.get(consignor_country.upper(), consignor_country)
            if consignee_country and len(consignee_country) == 2:
                consignee_country = ISO2_TO_COUNTRY.get(consignee_country.upper(), consignee_country)
                
            return {
                'consignor': {'name': consignor_name, 'street': consignor_street, 'city': consignor_city, 'country': consignor_country},
                'consignee': {'name': consignee_name, 'street': consignee_street, 'city': consignee_city, 'country': consignee_country},
            }

        # Prepare prompt (truncate large docs)
        doc_snippet = document
        try:
            serialized = _json.dumps(document, ensure_ascii=False)
            if len(serialized) > 12000:
                # Re-serialize a trimmed view to keep prompt size reasonable
                keys_to_keep = ['shipper', 'consignor', 'consignee', 'addresses', 'barcodes_and_numbers', 'raw_visible_text_snippets']
                doc_snippet = {k: document.get(k) for k in keys_to_keep if k in document}
        except Exception:
            doc_snippet = document

        system_instructions = (
            "You are given a shipping document (Air Waybill or Bill of Lading).\n"
            "Extract and return only the following information in JSON format:\n\n"
            "* Consignor (Shipper)\n  - Name\n  - Street (street address, building number, street name)\n  - City (city, town, or region name)\n  - Country (MUST be full country name like 'China', 'Jamaica', 'United States', NOT ISO codes)\n\n"
            "* Consignee\n  - Name\n  - Street (street address, building number, street name)\n  - City (city, town, or region name)\n  - Country (MUST be full country name like 'China', 'Jamaica', 'United States', NOT ISO codes)\n\n"
            "For country inference, use this priority:\n"
            "1. Explicit country names in address fields\n"
            "2. Convert ISO codes to full names (2-letter like 'CN'→'China', 'JM'→'Jamaica', 'US'→'United States')\n"
            "3. Airport codes (like 'MIA' for Miami→'United States', 'KIN' for Kingston→'Jamaica', 'HKG'→'Hong Kong')\n"
            "4. Seaport codes (like 'LAX' for Los Angeles→'United States', 'KIN' for Kingston→'Jamaica')\n"
            "5. City names that clearly indicate country (like 'Kingston'→'Jamaica', 'Miami'→'United States')\n\n"
            "IMPORTANT: Always return full country names, never ISO codes. If any field is missing, set its value to null. Return ONLY valid JSON without commentary."
        )

        example_json = {
            "consignor": {
                "name": "QI TAN",
                "street": "RM 808 BLOCK B 13/F TEXACO ROAD, INDUSTRIAL CENTRE 256-264 TEXACO RD",
                "city": "TSUEN WAN",
                "country": "Hong Kong"
            },
            "consignee": {
                "name": "RAFER JOHNSON",
                "street": "34 ROEHAMPTON CLOSE",
                "city": "KINGSTON",
                "country": "Jamaica"
            }
        }

        messages = [
            {"role": "system", "content": system_instructions},
            {"role": "user", "content": f"Document JSON:\n{_json.dumps(doc_snippet, ensure_ascii=False)}\n\nExample Output:\n{_json.dumps(example_json, ensure_ascii=False)}"}
        ]

        model = OPENROUTER_GENERAL_MODELS.get("kimi_standard")
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/klearrshipping/cudabot",
            "X-Title": "ESAD Address Party Extractor"
        }

        try:
            resp = _requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json={"model": model, "messages": messages, "temperature": 0.0, "max_tokens": 400},
                timeout=30,
            )
            if resp.status_code != 200:
                return _fallback_from_dict(document)
            payload = resp.json()
            content = payload["choices"][0]["message"]["content"].strip()
            # Strip code fences if any
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            result = _json.loads(content)

            # Normalize and ensure required keys
            consignor = result.get('consignor') or {}
            consignee = result.get('consignee') or {}
            
            # Convert ISO codes to full country names if needed
            consignor_country = consignor.get('country')
            if consignor_country and len(consignor_country) == 2:
                consignor_country = ISO2_TO_COUNTRY.get(consignor_country.upper(), consignor_country)
            
            consignee_country = consignee.get('country')
            if consignee_country and len(consignee_country) == 2:
                consignee_country = ISO2_TO_COUNTRY.get(consignee_country.upper(), consignee_country)
            
            out = {
                'consignor': {
                    'name': consignor.get('name') if consignor.get('name') not in ("", None) else None,
                    'street': consignor.get('street') if consignor.get('street') not in ("", None) else None,
                    'city': consignor.get('city') if consignor.get('city') not in ("", None) else None,
                    'country': consignor_country if consignor_country not in ("", None) else None,
                },
                'consignee': {
                    'name': consignee.get('name') if consignee.get('name') not in ("", None) else None,
                    'street': consignee.get('street') if consignee.get('street') not in ("", None) else None,
                    'city': consignee.get('city') if consignee.get('city') not in ("", None) else None,
                    'country': consignee_country if consignee_country not in ("", None) else None,
                },
            }
            # If LLM missed data, patch with fallback fields
            fb = _fallback_from_dict(document)
            if out['consignor']['name'] is None:
                out['consignor']['name'] = fb['consignor']['name']
            if out['consignor']['street'] is None:
                out['consignor']['street'] = fb['consignor']['street']
            if out['consignor']['city'] is None:
                out['consignor']['city'] = fb['consignor']['city']
            if out['consignor']['country'] is None:
                # Convert ISO to full name if needed
                fb_country = fb['consignor']['country']
                if fb_country and len(fb_country) == 2:
                    fb_country = ISO2_TO_COUNTRY.get(fb_country.upper(), fb_country)
                out['consignor']['country'] = fb_country
            if out['consignee']['name'] is None:
                out['consignee']['name'] = fb['consignee']['name']
            if out['consignee']['street'] is None:
                out['consignee']['street'] = fb['consignee']['street']
            if out['consignee']['city'] is None:
                out['consignee']['city'] = fb['consignee']['city']
            if out['consignee']['country'] is None:
                # Convert ISO to full name if needed
                fb_country = fb['consignee']['country']
                if fb_country and len(fb_country) == 2:
                    fb_country = ISO2_TO_COUNTRY.get(fb_country.upper(), fb_country)
                out['consignee']['country'] = fb_country
            
            # Final country inference attempt for any remaining null countries
            if not out['consignor']['country'] or not out['consignee']['country']:
                airport_consignor, airport_consignee = _infer_country_from_airports_ports(document)
                if not out['consignor']['country'] and airport_consignor:
                    out['consignor']['country'] = airport_consignor
                if not out['consignee']['country'] and airport_consignee:
                    out['consignee']['country'] = airport_consignee
            return out
        except Exception:
            return _fallback_from_dict(document)
    
    def format_address(self, address: str) -> FormattedAddress:
        """Use LLM to intelligently parse and format address with comprehensive country inference"""
        if not address:
            return FormattedAddress(
                original=address,
                formatted="",
                components=AddressComponent("", "", "", ""),
                confidence=0.0,
                issues=["Empty address provided"]
            )
        
        print(f"🔎 RAW Address Input: {address[:100]}...")
        
        # Use LLM for intelligent address parsing
        import json as _json
        import requests as _requests
        
        system_instructions = (
            "You are an expert address parser for customs documentation. Parse the following address and extract components.\n\n"
            "Use this comprehensive reference for country inference:\n"
            "1. ISO2 codes: US, JM, HK, CN, GB, etc.\n"
            "2. Airport codes: MIA (Miami/US), KIN (Kingston/Jamaica), HKG (Hong Kong), etc.\n"
            "3. Seaport codes: NYC (New York/US), KIN (Kingston/Jamaica), etc.\n"
            "4. City inference: Kingston/Montego Bay = Jamaica, Miami/New York = US, Hong Kong/Tsuen Wan = Hong Kong\n\n"
            "Return ONLY valid JSON in this exact format:\n"
            "{\n"
            '  "street_town": "street address or town",\n'
            '  "city": "city name",\n'
            '  "state_province_parish": "state/province/parish",\n'
            '  "country": "full country name",\n'
            '  "formatted_address": "Street, City, State/Province/Parish, Country"\n'
            "}\n\n"
            "If any field is missing or unclear, set to null. Return ONLY valid JSON without commentary."
        )
        
        messages = [
            {"role": "system", "content": system_instructions},
            {"role": "user", "content": f"Parse this address: {address}"}
        ]
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/klearrshipping/cudabot",
            "X-Title": "ESAD Address Parser"
        }
        
        try:
            resp = _requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json={"model": self.primary_model, "messages": messages, "temperature": 0.0, "max_tokens": 400},
                timeout=15,
            )
            
            if resp.status_code == 200:
                payload = resp.json()
                content = payload["choices"][0]["message"]["content"].strip()
                
                # Clean JSON response
                if content.startswith("```json"):
                    content = content[7:]
                if content.endswith("```"):
                    content = content[:-3]
                
                result = _json.loads(content)
                
                street_town = result.get("street_town", "") or ""
                city = result.get("city", "") or ""
                state_province_parish = result.get("state_province_parish", "") or ""
                country = result.get("country", "") or ""
                formatted = result.get("formatted_address", "") or ""
                
                components = AddressComponent(
                    street_town=street_town,
                    city=city,
                    state_province_parish=state_province_parish,
                    country=country
                )
                
                print(f"✅ LLM Address Parsing: {formatted}")
                
                return FormattedAddress(
                    original=address,
                    formatted=formatted,
                    components=components,
                    confidence=0.9,
                    issues=[]
                )
            else:
                raise Exception(f"LLM API error: {resp.status_code}")
                
        except Exception as e:
            print(f"⚠️ LLM parsing failed, using fallback: {e}")
            
            # Enhanced fallback parsing using our comprehensive mappings
            parts = [part.strip() for part in address.split() if part.strip()]
            
            street_town = ""
            city = ""
            state_province_parish = ""
            country = ""
            
            # Try to identify country using our comprehensive mappings
            country_found = None
            for i, part in enumerate(parts):
                if len(part) <= 3 and part.isalpha() and len(part) >= 2:
                    potential_country = _infer_country_from_codes(part)
                    if potential_country:
                        country_found = potential_country
                        parts = [p for j, p in enumerate(parts) if j != i]
                        break
            
            if country_found:
                country = country_found
            
            # Parse remaining parts
            if len(parts) >= 1:
                street_town = parts[0]
            if len(parts) >= 2:
                city = parts[1]
            if len(parts) >= 3:
                state_province_parish = parts[2]
            
            components = AddressComponent(
                street_town=street_town,
                city=city,
                state_province_parish=state_province_parish,
                country=country
            )
            
            formatted = ", ".join([part for part in [street_town, city, state_province_parish, country] if part])
            
            print(f"✅ Fallback Address Parsing: {formatted}")
        
        return FormattedAddress(
                original=address,
            formatted=formatted,
            components=components,
                confidence=0.5,
                issues=[f"LLM failed, used fallback: {str(e)}"]
            )

def main():
    """Main function to demonstrate enhanced address processing with clean JSON output"""
    formatter = AddressFormatter()

    # Example usage
    sample_document = {
        "shipper": {
            "name": "QI TAN",
            "address_line1": "RM 808 BLOCK B 13/F TEXACO ROAD, INDUSTRIAL CENTRE 256-264 TEXACO RD",
            "city": "TSUEN WAN",
            "country": "HK"
        },
        "consignee": {
            "name": "RAFER JOHNSON",
            "address_line1": "34 ROEHAMPTON CLOSE",
            "city": "KINGSTON",
            "country": "JM"
        }
    }
    
    print("🏠 Testing Address Processing Module...")
    
    # Test address formatting
    test_addresses = [
        "123 Main Street, Kingston, St. Andrew, Jamaica",
        "Unit C, 15th Floor, Building A, South China Digital Valley, Huanan Road, Minzhi Street, Longhua District, Shenzhen, Guangdong, China"
    ]
    
    results = []
    for address in test_addresses:
        formatted = formatter.format_address(address)
        results.append({
            'formatted': formatted.formatted,
            'confidence': formatted.confidence
        })
    
    # Display clean JSON result
    clean_result = {
        "success": True,
        "formatted_addresses": results
    }
    
    print(f"\n📋 Final Result: {json.dumps(clean_result, indent=2, ensure_ascii=False)}")

if __name__ == "__main__":
    main()
