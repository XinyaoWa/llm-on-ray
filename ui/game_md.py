import re

attribute_list = ['name', 'exp_release_date', 'release_year', 'developer', 'esrb', 'rating', 'genres', 'player_perspective', 'has_multiplayer', 'platforms', 'available_on_steam', 'has_linux_release', 'has_mac_release', 'specifier']

def get_pair_dict(output_str):
    if output_str.endswith("</s>"):
        output_str = output_str[:-4]

    format2 = ".*[\[][^\[\]]*[\]]$"
    str_attributes_new = None
    str_attributes = output_str
    
    if "], " in str_attributes:
        str_attributes = str_attributes.split("], ")
    elif "]," in str_attributes:
        str_attributes = str_attributes.split("],")
    else:
        str_attributes = [str_attributes]
    
    str_attributes_new = []
    num_attributes = len(str_attributes)
    for i in range(num_attributes):
        attribute = str_attributes[i] + "]" if i < (num_attributes-1) else str_attributes[i]
        if re.match(format2, attribute):
            str_attributes_new.append(attribute)

    num_attributes = len(str_attributes_new)
    if num_attributes == 0:
        return
    str_attributes_name = []
    str_attributes_dict = {}
    for attribute in str_attributes_new:
        attribute_name, attribute_value = attribute.split("[")
        attribute_value = attribute_value[:-1]
        if attribute_name in attribute_list:
            str_attributes_name.append(attribute_name)
            str_attributes_dict[attribute_name] = attribute_value
    return str_attributes_dict

def get_md(pair_dicts):
    num = len(pair_dicts)
    keys = set()
    for pair_dict in pair_dicts:
        keys = keys.union(pair_dict.keys())

    name_mds = "\n|"
    split_mds = "|"
    value_mds = ["|"]*num
    for attribute in attribute_list:
        if attribute in keys:
            name_mds += attribute + "|"
            split_mds += "----|"
            for i in range(num):
                if attribute in pair_dicts[i].keys():
                    value_mds[i] += pair_dicts[i][attribute] + "|"
                else:
                    value_mds[i] += "|"
    output_md = name_mds + "\n" + split_mds + "\n"
    for value_md in value_mds:
        output_md += value_md + "\n"
    return output_md

def get_game_md(output_strs):
    output_strs = output_strs.split("\n")
    pair_dicts = []
    for output_str in output_strs:
        if len(output_str) > 0:
            pair_dict = get_pair_dict(output_str)
            if pair_dict is not None:
                pair_dicts.append(pair_dict)
    output_md = get_md(pair_dicts)
    return output_md