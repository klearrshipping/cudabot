import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import json
from datetime import datetime
import requests
import os
from config import OPENROUTER_API_KEY
from config import OPENROUTER_GENERAL_MODELS

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
    'JAX': 'United States', 'TAM': 'United States', 'TAM': 'United States', 'TAM': 'United States',
    'KIN': 'Jamaica', 'KIN': 'Jamaica', 'KIN': 'Jamaica', 'KIN': 'Jamaica',
    'HKG': 'Hong Kong', 'SHA': 'China', 'TSN': 'China', 'QIN': 'China', 'DAL': 'China',
    'NGB': 'China', 'FOC': 'China', 'XMN': 'China', 'ZHA': 'China', 'YAN': 'China',
    'YOK': 'Japan', 'OSA': 'Japan', 'NAG': 'Japan', 'KOB': 'Japan', 'HAK': 'Japan',
    'BUS': 'South Korea', 'INC': 'South Korea', 'PUS': 'South Korea', 'ULS': 'South Korea',
    'SIN': 'Singapore', 'KUL': 'Malaysia', 'PEN': 'Malaysia', 'JOH': 'Malaysia',
    'BKK': 'Thailand', 'LCH': 'Thailand', 'SON': 'Thailand', 'SAT': 'Thailand',
    'MNL': 'Philippines', 'CEB': 'Philippines', 'DVO': 'Philippines', 'ILO': 'Philippines',
    'JKT': 'Indonesia', 'SBY': 'Indonesia', 'MDN': 'Indonesia', 'PLM': 'Indonesia',
    'BOM': 'India', 'CAL': 'India', 'MAA': 'India', 'COC': 'India', 'VIZ': 'India',
    'CCU': 'India', 'KAN': 'India', 'PAR': 'India', 'GOA': 'India', 'COC': 'India',
    'DXB': 'United Arab Emirates', 'AUH': 'United Arab Emirates', 'SHJ': 'United Arab Emirates',
    'DOH': 'Qatar', 'KWI': 'Kuwait', 'BAH': 'Bahrain', 'RUH': 'Saudi Arabia',
    'JED': 'Saudi Arabia', 'DAM': 'Saudi Arabia', 'IST': 'Turkey', 'IZM': 'Turkey',
    'MER': 'Turkey', 'SAM': 'Turkey', 'TLV': 'Israel', 'HAI': 'Israel', 'ASH': 'Israel',
    'CAI': 'Egypt', 'ALE': 'Egypt', 'DAM': 'Egypt', 'POR': 'Egypt', 'SUE': 'Egypt',
    'JNB': 'South Africa', 'CPT': 'South Africa', 'DUR': 'South Africa', 'PLZ': 'South Africa',
    'LON': 'United Kingdom', 'LIV': 'United Kingdom', 'MAN': 'United Kingdom', 'BIR': 'United Kingdom',
    'GLA': 'United Kingdom', 'EDI': 'United Kingdom', 'BEL': 'United Kingdom', 'CAR': 'United Kingdom',
    'PAR': 'France', 'MAR': 'France', 'LYO': 'France', 'NIC': 'France', 'BOR': 'France',
    'LEH': 'France', 'TOU': 'France', 'HAR': 'France', 'DUN': 'France', 'CAL': 'France',
    'HAM': 'Germany', 'BRE': 'Germany', 'HAM': 'Germany', 'KIE': 'Germany', 'LUE': 'Germany',
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
    'BUE': 'Argentina', 'COR': 'Argentina', 'MEN': 'Argentina', 'ROS': 'Argentina', 'MEN': 'Argentina',
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
    'SAN': 'El Salvador', 'SAN': 'El Salvador', 'SAN': 'El Salvador', 'SAN': 'El Salvador', 'SAN': 'El Salvador',
    'MAN': 'Nicaragua', 'LEO': 'Nicaragua', 'GRA': 'Nicaragua', 'EST': 'Nicaragua', 'CHI': 'Nicaragua',
    'BEL': 'Belize', 'BEL': 'Belize', 'BEL': 'Belize', 'BEL': 'Belize', 'BEL': 'Belize',
    'CAN': 'Mexico', 'MEX': 'Mexico', 'GUA': 'Mexico', 'MON': 'Mexico', 'TIJ': 'Mexico',
    'PUE': 'Mexico', 'MER': 'Mexico', 'LEO': 'Mexico', 'TOR': 'Mexico', 'HER': 'Mexico',
    'HAV': 'Cuba', 'SAN': 'Cuba', 'CAM': 'Cuba', 'BAY': 'Cuba', 'HOL': 'Cuba',
    'SAN': 'Dominican Republic', 'PUE': 'Dominican Republic', 'LA': 'Dominican Republic', 'ROM': 'Dominican Republic', 'HER': 'Dominican Republic',
    'SAN': 'Puerto Rico', 'PON': 'Puerto Rico', 'MAY': 'Puerto Rico', 'AGU': 'Puerto Rico', 'FAJ': 'Puerto Rico',
    'BRI': 'Barbados', 'BRI': 'Barbados', 'BRI': 'Barbados', 'BRI': 'Barbados', 'BRI': 'Barbados',
    'POR': 'Trinidad and Tobago', 'SAN': 'Trinidad and Tobago', 'CHA': 'Trinidad and Tobago', 'COU': 'Trinidad and Tobago', 'SCA': 'Trinidad and Tobago',
    'SAI': 'Grenada', 'SAI': 'Grenada', 'SAI': 'Grenada', 'SAI': 'Grenada', 'SAI': 'Grenada',
    'CAS': 'Saint Lucia', 'CAS': 'Saint Lucia', 'CAS': 'Saint Lucia', 'CAS': 'Saint Lucia', 'CAS': 'Saint Lucia',
    'SAI': 'Antigua and Barbuda', 'SAI': 'Antigua and Barbuda', 'SAI': 'Antigua and Barbuda', 'SAI': 'Antigua and Barbuda', 'SAI': 'Antigua and Barbuda',
    'BAS': 'Saint Kitts and Nevis', 'BAS': 'Saint Kitts and Nevis', 'BAS': 'Saint Kitts and Nevis', 'BAS': 'Saint Kitts and Nevis', 'BAS': 'Saint Kitts and Nevis',
    'KIN': 'Saint Vincent and the Grenadines', 'KIN': 'Saint Vincent and the Grenadines', 'KIN': 'Saint Vincent and the Grenadines', 'KIN': 'Saint Vincent and the Grenadines', 'KIN': 'Saint Vincent and the Grenadines',
    'ROS': 'Dominica', 'ROS': 'Dominica', 'ROS': 'Dominica', 'ROS': 'Dominica', 'ROS': 'Dominica',
    'SCA': 'Tobago', 'SCA': 'Tobago', 'SCA': 'Tobago', 'SCA': 'Tobago', 'SCA': 'Tobago',
    'PRO': 'Turks and Caicos Islands', 'PRO': 'Turks and Caicos Islands', 'PRO': 'Turks and Caicos Islands', 'PRO': 'Turks and Caicos Islands', 'PRO': 'Turks and Caicos Islands',
    'NAS': 'Bahamas', 'FRE': 'Bahamas', 'GEO': 'Bahamas', 'EXU': 'Bahamas', 'ELE': 'Bahamas',
    'GEO': 'Cayman Islands', 'GEO': 'Cayman Islands', 'GEO': 'Cayman Islands', 'GEO': 'Cayman Islands', 'GEO': 'Cayman Islands',
    'CAS': 'Saint Lucia', 'CAS': 'Saint Lucia', 'CAS': 'Saint Lucia', 'CAS': 'Saint Lucia', 'CAS': 'Saint Lucia',
    'HAM': 'Bermuda', 'HAM': 'Bermuda', 'HAM': 'Bermuda', 'HAM': 'Bermuda', 'HAM': 'Bermuda',
    'PHI': 'Sint Maarten', 'PHI': 'Sint Maarten', 'PHI': 'Sint Maarten', 'PHI': 'Sint Maarten', 'PHI': 'Sint Maarten',
    'ROA': 'Anguilla', 'ROA': 'Anguilla', 'ROA': 'Anguilla', 'ROA': 'Anguilla', 'ROA': 'Anguilla',
    'ROA': 'British Virgin Islands', 'ROA': 'British Virgin Islands', 'ROA': 'British Virgin Islands', 'ROA': 'British Virgin Islands', 'ROA': 'British Virgin Islands',
    'CHA': 'United States Virgin Islands', 'CHA': 'United States Virgin Islands', 'CHA': 'United States Virgin Islands', 'CHA': 'United States Virgin Islands', 'CHA': 'United States Virgin Islands'
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

def _web_search_country(query: str) -> Optional[str]:
    """Search for country information using web search as last resort."""
    try:
        # This would require implementing a web search API
        # For now, return None to avoid external dependencies
        return None
    except Exception:
        return None

def extract_consignor_consignee(document: dict) -> dict:
    """
    Using the preferred LLM model, extract consignor (shipper) and consignee
    name, street, city, and combined address from a shipping document (AWB/BOL).

    Returns a dict with keys: {"consignor": {"name": str|None, "street": str|None, "city": str|None, "address": str|None, "country": str|None},
    "consignee": {"name": str|None, "street": str|None, "city": str|None, "address": str|None, "country": str|None}}
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
        
        return {
            'consignor': {'name': consignor_name, 'street': consignor_street, 'city': consignor_city, 'address': consignor_addr, 'country': consignor_country},
            'consignee': {'name': consignee_name, 'street': consignee_street, 'city': consignee_city, 'address': consignee_addr, 'country': consignee_country},
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
        "* Consignor (Shipper)\n  - Name\n  - Street (street address, building number, street name)\n  - City (city, town, or region name)\n  - Address (combine all address fields into one string if multiple are present)\n  - Country (establish from explicit text, 2-digit or 3-digit ISO country codes, or infer from any listed ports/airports if not explicitly stated)\n\n"
        "* Consignee\n  - Name\n  - Street (street address, building number, street name)\n  - City (city, town, or region name)\n  - Address (combine all address fields into one string if multiple are present)\n  - Country (establish from explicit text, 2-digit or 3-digit ISO country codes, or infer from any listed ports/airports if not explicitly stated)\n\n"
        "For country inference, use this priority:\n"
        "1. Explicit country names in address fields\n"
        "2. ISO country codes (2-letter like 'US', 'HK', 'JM' or 3-letter like 'USA', 'HKG', 'JAM')\n"
        "3. Airport codes (like 'MIA' for Miami/US, 'KIN' for Kingston/Jamaica, 'HKG' for Hong Kong)\n"
        "4. Seaport codes (like 'LAX' for Los Angeles/US, 'KIN' for Kingston/Jamaica)\n"
        "5. City names that clearly indicate country (like 'Kingston' likely Jamaica, 'Miami' likely US)\n\n"
        "If any field is missing, set its value to null. Return ONLY valid JSON without commentary."
    )

    example_json = {
        "consignor": {
            "name": "QI TAN",
            "street": "RM 808 BLOCK B 13/F TEXACO ROAD, INDUSTRIAL CENTRE 256-264 TEXACO RD",
            "city": "TSUEN WAN",
            "address": "RM 808 BLOCK B 13/F TEXACO ROAD, INDUSTRIAL CENTRE 256-264 TEXACO RD TSUEN WAN 76900, TSUEN WAN, HK",
            "country": "Hong Kong"
        },
        "consignee": {
            "name": "RAFER JOHNSON",
            "street": "34 ROEHAMPTON CLOSE",
            "city": "KINGSTON",
            "address": "34 ROEHAMPTON CLOSE, KINGSTON",
            "country": "Jamaica"
        }
    }

    messages = [
        {"role": "system", "content": system_instructions},
        {"role": "user", "content": f"Document JSON:\n{_json.dumps(doc_snippet, ensure_ascii=False)}\n\nExample Output:\n{_json.dumps(example_json, ensure_ascii=False)}"}
    ]

    model = OPENROUTER_GENERAL_MODELS.get("gpt_4o")
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
        out = {
            'consignor': {
                'name': consignor.get('name') if consignor.get('name') not in ("", None) else None,
                'street': consignor.get('street') if consignor.get('street') not in ("", None) else None,
                'city': consignor.get('city') if consignor.get('city') not in ("", None) else None,
                'address': consignor.get('address') if consignor.get('address') not in ("", None) else None,
                'country': consignor.get('country') if consignor.get('country') not in ("", None) else None,
            },
            'consignee': {
                'name': consignee.get('name') if consignee.get('name') not in ("", None) else None,
                'street': consignee.get('street') if consignee.get('street') not in ("", None) else None,
                'city': consignee.get('city') if consignee.get('city') not in ("", None) else None,
                'address': consignee.get('address') if consignee.get('address') not in ("", None) else None,
                'country': consignee.get('country') if consignee.get('country') not in ("", None) else None,
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
        if out['consignor']['address'] is None:
            out['consignor']['address'] = fb['consignor']['address']
        if out['consignor']['country'] is None:
            out['consignor']['country'] = fb['consignor']['country']
        if out['consignee']['name'] is None:
            out['consignee']['name'] = fb['consignee']['name']
        if out['consignee']['street'] is None:
            out['consignee']['street'] = fb['consignee']['street']
        if out['consignee']['city'] is None:
            out['consignee']['city'] = fb['consignee']['city']
        if out['consignee']['address'] is None:
            out['consignee']['address'] = fb['consignee']['address']
        if out['consignee']['country'] is None:
            out['consignee']['country'] = fb['consignee']['country']
        
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


