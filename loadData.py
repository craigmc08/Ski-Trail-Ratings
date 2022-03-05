import pandas as pd
from os.path import exists
import time
from tqdm import tqdm
import csv
from decimal import Decimal
import draw_map

import helper
import saveData
import osmHelper

# accepts a osm filename and a blacklist name and returns a list of tuples.
# Each tuple contains a dataframe with
# 4 columns: latitude, longitude, lat/lon pairs, and elevation (meters)
# a string with the trailname,
# and an int (0-1) to denote if the trail is gladed


def generate_trails_and_lifts(mountain, blacklist=''):
    filename = mountain + '.osm'
    cached_filename = mountain + '.csv'
    if not exists('osm/{}'.format(filename)):
        print('OSM file missing')
        return (-1, -1)
    if not exists('cached/osm_ids/{}.csv'.format(blacklist)) and blacklist != '':
        print('Blacklist file missing')

    file = open('osm/{}'.format(filename), 'r')
    raw_table = file.readlines()

    if blacklist != '':
        blacklist_ids = (pd.read_csv(
            'cached/osm_ids/{}.csv'.format(blacklist)))['id'].to_list()
        blacklist_ids = [str(x) for x in blacklist_ids]
    else:
        blacklist_ids = []

    whitelist_mode = False
    if blacklist == mountain:
        whitelist_mode = True
    node_df, way_df, lift_df, useful_info_list, total_trail_count, trail_and_id_list = osmHelper.process_osm(
        raw_table, blacklist_ids, whitelist_mode)

    saveData.save_trail_ids(trail_and_id_list, mountain + '.csv')

    cached = True
    if not exists('cached/trail_points/{}'.format(cached_filename)) and cached:
        cached = False
        print('Disabling cache loading: no cache file found.')

    trail_list = []
    api_requests = 0
    if cached:
        elevation_df = pd.read_csv(
            'cached/trail_points/{}'.format(cached_filename))
        elevation_df['coordinates'] = [
            (round(Decimal(x), 8), round(Decimal(y),8)) for x, y in zip(elevation_df.lat, elevation_df.lon)]
        ele_dict = dict(zip(elevation_df.coordinates, elevation_df.elevation))
    last_called = time.time()
    for column, _ in zip(way_df, tqdm(range(total_trail_count), desc="Loading Trails…", ascii=False, ncols=75)):
        temp_df = pd.merge(way_df[column], node_df,
                           left_on=column, right_on='id')
        del temp_df['id']
        del temp_df[column]
        temp_df = helper.fill_in_point_gaps(temp_df, 15)
        temp_df['coordinates'] = [(round(Decimal(x[0]), 8), round(Decimal(x[1]), 8))
                                  for x in temp_df.coordinates]

        for row in useful_info_list:
            if column == row[0]:
                difficulty_modifier = row[1]
                area_flag = row[2]
                way_id = row[3]
        try:
            temp_df['elevation'] = [ele_dict[x] for x in temp_df.coordinates]
        except:
            result = helper.get_elevation(
                temp_df['coordinates'], last_called, column, api_requests)
            temp_df['elevation'] = result[0]
            api_requests = result[1]
            last_called = result[2]
        temp_area_line_df = pd.DataFrame()
        if area_flag:
            temp_area_line_df = helper.area_to_line(temp_df)
            temp_area_line_df['coordinates'] = [
                (round(Decimal(x[0]), 8), round(Decimal(x[1]), 8)) for x in temp_area_line_df.coordinates]
            try:
                temp_area_line_df['elevation'] = [ele_dict[x]
                                                  for x in temp_area_line_df.coordinates]
            except:
                result = helper.get_elevation(
                    temp_area_line_df['coordinates'], last_called, column, api_requests)
                temp_area_line_df['elevation'] = result[0]
                api_requests = result[1]
                last_called = result[2]
        trail_list.append((temp_df, column, difficulty_modifier,
                          area_flag, temp_area_line_df, way_id))
    lift_list = []
    for column in lift_df:
        temp_df = pd.merge(lift_df[column], node_df,
                           left_on=column, right_on='id')
        temp_df = helper.fill_in_point_gaps(temp_df, 50)
        lift_list.append((temp_df, column))
    if total_trail_count == 0:
        print('No trails found.')
        return (-1, -1)
    print('{} API requests made'.format(api_requests))

    return (trail_list, lift_list)

# Parameters:
# mountain: name of ski area
#   type-string
# cardinal_direction: which way does the ski area face
#   type-string
#   valid options-'n','s','e','w'
# save_map: whethere to save the output to an svg file
#   type-bool
# blacklist: name of nearby ski area to ignore trails and lifts from
#   type-string
#
# Return: the relative difficultly and ease of the difficult and beginner terrain
#   type-tuple(float,float)


def process_mountain(mountain, cardinal_direction, save_map=False, blacklist=''):
    trail_list, lift_list = generate_trails_and_lifts(mountain, blacklist)
    if trail_list == -1:
        return -1

    finished_trail_list = []
    for entry in trail_list:
        if not entry[3]:
            trail = entry[0]
        else:
            trail = entry[4]
            perimeter = entry[0]
            perimeter['distance'] = helper.calculate_dist(
                perimeter['coordinates'])
            perimeter['elevation_change'] = helper.calulate_elevation_change(
                perimeter['elevation'])
            perimeter['slope'] = helper.calculate_slope(
                perimeter['elevation_change'], perimeter['distance'])

        trail['elevation'] = helper.smooth_elevations(
            trail['elevation'].to_list(), 0)
        trail['distance'] = helper.calculate_dist(trail['coordinates'])
        trail['elevation_change'] = helper.calulate_elevation_change(
            trail['elevation'])
        trail['slope'] = helper.calculate_slope(
            trail['elevation_change'], trail['distance'])
        trail['difficulty'] = helper.calculate_point_difficulty(trail['slope'])
        if not entry[3]:
            finished_trail_list.append(
                (trail, entry[1], entry[2], entry[3], entry[4], entry[5]))
        else:
            finished_trail_list.append(
                (perimeter, entry[1], entry[2], entry[3], trail, entry[5]))

    svg = draw_map.draw_mountain(finished_trail_list, lift_list, mountain, cardinal_direction)
    with open('tmp.svg', 'w') as f:
        f.write(svg)
    return

    mtn_difficulty = saveData.create_map(
        finished_trail_list, lift_list, mountain, cardinal_direction, save_map)
    if mtn_difficulty == -1:
        return -1
    vert = helper.calculate_mtn_vert(finished_trail_list)
    saveData.cache_trail_points(mountain + '.csv', trail_list)
    output = (mtn_difficulty[0], mtn_difficulty[1],
              round(vert), len(trail_list), len(lift_list))
    return output

# Parameters:
# mountain: name of ski area
#   type-str
# direction: orientation of map
#   type-char
# save_map: whether to save the map
#   type-bool
# blacklist: any mountains to exclude trails from
#   type-str
# location: state ski area is in
#   type-str
#
# Return: -1 for failure, 0 otherwise
#   type-int


def osm(mountain='', direction='', save_map=False, blacklist='', location=''):
    print('\nProcessing {}'.format(helper.format_name(mountain)))
    mountain_df = pd.read_csv('mountain_list.csv')
    previously_run = False
    if mountain in mountain_df.mountain.to_list():
        previously_run = True
        mountain_row = mountain_df.loc[mountain_df.mountain == mountain]
    if direction == '' and previously_run:
        value = mountain_row.direction.to_list()[0]
        if str(value) != 'nan':
            direction = value
    if blacklist == '' and previously_run:
        value = mountain_row.blacklist.to_list()[0]
        if str(value) != 'nan':
            blacklist = value
    if location == '' and previously_run:
        value = mountain_row.state.to_list()[0]
        if str(value) != 'nan':
            location = value
    diff_tuple = process_mountain(mountain, direction, save_map, blacklist)
    if diff_tuple == -1:
        return -1
    if save_map and exists('mountain_list.csv'):
        # row = (mountain, direction, state, region, difficulty, ease, vert, trail_count, lift_count, blacklist)
        row = [[mountain, direction, location, helper.assign_region(location), diff_tuple[0], diff_tuple[1],
                diff_tuple[2], diff_tuple[3], diff_tuple[4], blacklist]]
        if previously_run:
            mountain_df.loc[mountain_df.mountain == mountain] = row
            output = mountain_df
        else:
            row = pd.Series(row[0], index=mountain_df.columns)
            output = mountain_df.append(row, ignore_index=True)
            output.sort_values(by=['mountain'], inplace=True)
        output['trail_count'] = output['trail_count'].astype(int)
        output['lift_count'] = output['lift_count'].astype(int)
        output.to_csv('mountain_list.csv', index=False)
    else:
        print('Mountain data not saved. If this is unexpected, please make sure you have a file called mountain_list.csv')
    return 0

# Parameters:
# input_csv: name of csv
#   type-str
# save_map: whether to save the map
#   type-bool
#
# Return: none


def bulk_osm(input_csv, save_map=False):
    if input_csv[:-4] != '.csv':
        input_csv = input_csv + '.csv'
    with open(input_csv, mode='r') as file:
        csv_file = csv.reader(file)
        next(csv_file)
        for line in csv_file:
            if len(line) == 0:
                break
            if line[0][0] == '#':
                continue
            osm(line[0], line[1], save_map, line[9], line[2])

# Parameters:
# save_output: whether to save the map
#   type-bool
#
# Return: none


def barplot(save_output=False):
    if not exists('mountain_list.csv'):
        print('Missing cache files, please run bulk_osm or osm and set save_map=True.')
        return
    df = pd.read_csv('mountain_list.csv')
    df['mountain'] = [helper.format_name(x) for x in df['mountain']]
    saveData.create_difficulty_barplot(df, 'USA' ,save_output)

    state_list = df.state.unique()
    for state in state_list:
        if len(state.split()) > 1:
            continue
        temp_df = df[df['state'].str.contains(state)]
        region = helper.assign_region(state)
        saveData.create_difficulty_barplot(temp_df, f'{region}/{state}', save_output)
    for region in ['northeast', 'southeast', 'midwest', 'west']:
        temp_df = df.loc[df['region'] == region]
        saveData.create_difficulty_barplot(temp_df, helper.format_name(region), save_output)      

