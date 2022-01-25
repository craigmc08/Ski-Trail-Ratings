import pandas as pd
from os.path import exists
from ast import literal_eval
import time
from tqdm import tqdm

import helper
import saveData

# accepts a gpx filename and returns a dataframe
# with 4 columns: latitude, longitude, lat/lon pairs and elevation (meters)


def load_gpx(filename):
    raw_table = pd.read_csv(filename).to_numpy()
    df = pd.DataFrame()
    lat = []
    lon = []
    coordinates = []
    elevation = []
    for row in raw_table:
        row = str(row)
        if 'trkpt lat' in row:
            split_row = row.split('"')
            lat.append(float(split_row[1]))
            lon.append(float(split_row[3]))
            coordinates.append((float(split_row[1]), float(split_row[3])))
        if 'ele' in row:
            elevation.append(float(row.split('>')[1].split('<')[0]))
    df['lat'] = lat
    df['lon'] = lon
    df['coordinates'] = coordinates
    df['elevation'] = elevation
    return df

# Parameters:
# filename: name of gpx file. GPX file should contain 1 trail.
#   type-string
#
# Return Type: none


def runGPX(filename):
    df = load_gpx(filename)
    df = helper.fill_in_point_gaps(df, 15, 'gpx')
    df['elevation'] = helper.smooth_elevations(df['elevation'].to_list())
    df['distance'] = helper.calculate_dist(df['coordinates'])
    df['elevation_change'] = helper.calulate_elevation_change(df['elevation'])
    df['slope'] = helper.calculate_slope(
        df['elevation_change'], df['distance'])
    df['difficulty'] = helper.calculate_point_difficulty(df['slope'].to_list())
    saveData.create_gpx_map(df)

# accepts a osm filename and returns a list of tuples.
# Each tuple contains a dataframe with
# 4 columns: latitude, longitude, lat/lon pairs, and elevation (meters)
# a string with the trailname,
# and an int (0-1) to denote if the trail is gladed


def load_osm(mountain, cached=True, blacklist=''):
    filename = mountain + '.osm'
    if cached:
        cached_filename = mountain + '.csv'
    if not exists('osm/{}'.format(filename)):
        print('OSM file missing')
        return (-1, -1)
    if not exists('cached/osm_ids/{}'.format(blacklist)) and blacklist != '':
        print('Blacklist file missing')

    file = open('osm/{}'.format(filename), 'r')
    raw_table = file.readlines()

    if blacklist != '':
        blacklist_ids = (pd.read_csv('cached/osm_ids/{}'.format(blacklist)))['id'].to_list()
        blacklist_ids = [str(x) for x in blacklist_ids]
    else:
        blacklist_ids = []
    
    node_df, way_df, lift_df, useful_info_list, total_trail_count, trail_and_id_list = helper.process_osm(raw_table, blacklist_ids)
    
    saveData.save_trail_ids(trail_and_id_list, mountain)

    if not exists('cached/elevation/{}'.format(cached_filename)) and cached:
        cached = False
        print('Disabling cache loading: no cache file found.')

    trail_list = []
    trail_num = 0
    api_requests = 0
    if cached:
        elevation_df = pd.read_csv('cached/elevation/{}'.format(cached_filename), converters={
                                   'coordinates': literal_eval})
        elevation_df = elevation_df[['coordinates', 'elevation']]
        elevation_df.drop_duplicates(inplace=True)
    last_called = time.time()
    for column, _ in zip(way_df, tqdm (range(total_trail_count-1), desc="Loading Trails…", ascii=False, ncols=75)):
        trail_num += 1
        temp_df = pd.merge(way_df[column], node_df,
                           left_on=column, right_on='id')
        del temp_df['id']
        del temp_df[column]
        temp_df = helper.fill_in_point_gaps(temp_df, 15)
        for row in useful_info_list:
            if column == row[0]:
                difficulty_modifier = row[1]
                area_flag = row[2]
        if not cached:
            result = helper.get_elevation(
                temp_df['coordinates'], last_called, column, api_requests)
            temp_df['elevation'] = result[0]
            api_requests = result[1]
            last_called = result[2]
        else:
            row_count = temp_df.shape[0]
            temp_df_2 = pd.merge(temp_df, elevation_df, on='coordinates')
            # if cache is missing data
            if temp_df_2.shape[0] < row_count:
                result = helper.get_elevation(
                    temp_df['coordinates'], last_called, column, api_requests)
                temp_df['elevation'] = result[0]
                api_requests = result[1]
                last_called = result[2]
            else:
                temp_df = temp_df_2
        temp_area_line_df = pd.DataFrame()
        if area_flag:
            temp_area_line_df = helper.area_to_line(temp_df)
            if not cached:
                result = helper.get_elevation(
                    temp_area_line_df['coordinates'], last_called, column, api_requests)
                temp_area_line_df['elevation'] = result[0]
                api_requests = result[1]
                last_called = result[2]
            else:
                row_count = temp_area_line_df.shape[0]
                temp_area_line_df_2 = pd.merge(temp_area_line_df, elevation_df, on='coordinates')
                # if cache is missing data
                if temp_area_line_df_2.shape[0] < row_count:
                    result = helper.get_elevation(
                        temp_area_line_df['coordinates'], last_called, column, api_requests)
                    temp_area_line_df['elevation'] = result[0]
                    api_requests = result[1]
                    last_called= result[2]
                else:
                    temp_area_line_df = temp_area_line_df_2
        trail_list.append((temp_df, column, difficulty_modifier, area_flag, temp_area_line_df))
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
#   valid options-'n','s','e','w' or some combination of the 4
# save_map: whethere to save the output to an svg file
#   type-bool
# blacklist: name of nearby ski area to ignore trails and lifts from
#   type-string
#
# Return: the relative difficultly and ease of the difficult and beginner terrain
#   type-tuple(float,float)


def runOSM(mountain, cardinal_direction, save_map=False, blacklist=''):
    trail_list, lift_list = load_osm(mountain, True, blacklist)
    if trail_list == -1:
        return -1

    finished_trail_list = []
    for entry in trail_list:
        if not entry[3]:
            trail = entry[0]
        else:
            trail = entry[4]
        trail['elevation'] = helper.smooth_elevations(
            trail['elevation'].to_list(), 0)
        trail['distance'] = helper.calculate_dist(trail['coordinates'])
        trail['elevation_change'] = helper.calulate_elevation_change(
            trail['elevation'])
        trail['slope'] = helper.calculate_slope(
            trail['elevation_change'], trail['distance'])
        trail['difficulty'] = helper.calculate_point_difficulty(trail['slope'])
        if not entry[3]:
            finished_trail_list.append((trail, entry[1], entry[2], entry[3], entry[4]))
        else:
            finished_trail_list.append((entry[0], entry[1], entry[2], entry[3], trail))

    mtn_difficulty = saveData.create_map(
        finished_trail_list, lift_list, mountain, cardinal_direction, save_map)
    if mtn_difficulty == -1:
        return -1
    vert = helper.calculate_mtn_vert(finished_trail_list)
    saveData.cache_elevation(mountain + '.csv', trail_list)
    output = (mtn_difficulty[0], mtn_difficulty[1], round(vert))
    return output
