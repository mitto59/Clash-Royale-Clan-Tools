#!/usr/bin/python
"""Tools for creating a clan maagement dashboard for Clash Royale."""

__license__   = 'LGPLv3'
__docformat__ = 'reStructuredText'

import codecs
from datetime import datetime
from jinja2 import Environment, PackageLoader, select_autoescape
import json
import os
import requests
import shutil
import tempfile
import urllib
import urllib.parse
from ._version import __version__

def write_object_to_file(file_path, obj): 
    """ Writes contents of object to file. If object is a string, write it 
    directly. Otherwise, convert it to JSON first """

    # open file for UTF-8 output, and write contents of object to file
    with codecs.open(file_path, 'w', 'utf-8') as f:
        if isinstance(obj, str) or isinstance(obj, unicode):
            string = obj
        else:
            string = json.dumps(obj, indent=4)
        f.write(string)

def get_clan(api_key, clan_id):
    """Grab clan data from API."""

    # curl -X GET --header 'Accept: application/json' --header "authorization: Bearer <API token>" 'https://api.clashroyale.com/v1/clans/%23JY8YVV'
    url = 'https://api.clashroyale.com/v1/clans/' + urllib.parse.quote_plus(clan_id)
    headers = {
        'Accept': 'application/json',
        'authorization': 'Bearer ' + api_key
    }
    r = requests.get(url, headers=headers)
    clan = json.loads(r.text)

    return clan

def get_warlog(api_key, clan_id):
    """Grab war log data from API."""

    # curl -X GET --header 'Accept: application/json' --header "authorization: Bearer <API token>" 'https://api.clashroyale.com/v1/clans/%23JY8YVV/warlog'
    url = 'https://api.clashroyale.com/v1/clans/' + urllib.parse.quote_plus(clan_id) + '/warlog?limit=20'
    headers = {
        'Accept': 'application/json',
        'authorization': 'Bearer ' + api_key
    }
    r = requests.get(url, headers=headers)
    warlog = json.loads(r.text)

    return warlog['items']

def warlog_dates(warlog):
    """ Return list of date strings from warlog. One entry per war. """

    war_dates = []
    for war in warlog:
        war_dates.append(datetime.strptime(war['createdDate'].split('.')[0], '%Y%m%dT%H%M%S').strftime("%m-%d"))
    return war_dates


def member_warlog(member_tag, warlog):
    """ Return war participation records for a given member by member tag. """

    member_warlog = []
    for war in warlog:
        participation = {'status': 'na'}
        for member in war['participants']:
            if member['tag'] == member_tag:
                if member['collectionDayBattlesPlayed'] == 0:
                    member['status'] = 'na'
                elif member['battlesPlayed'] == 0:
                    member['status'] = 'bad'
                elif member['collectionDayBattlesPlayed'] < 3:
                    member['status'] = 'ok'
                else:
                    member['status'] = 'good'
                participation = member
        member_warlog.append(participation)
    return member_warlog

def member_danger(member, member_warlog):
    good = ok = bad = 0
    for war in member_warlog:
        if war != None:
            if war['status'] == 'good':
                good += 1
            elif war['status'] == 'ok':
                ok += 1
            elif war['status'] == 'bad':
                bad += 1

    if bad > good:
        return True
    if good == 0 and member['donations'] == 0:
        return True

    return False

def render_dashboard(env, members, clan_name, clan_id, clan_description, clan_min_trophies, clan_stats, war_dates):
    """Render clan dashboard."""

    member_table = env.get_template('member-table.html.j2').render(
        members      = members, 
        clan_name    = clan_name, 
        min_trophies = clan_min_trophies, 
        war_dates    = war_dates
    )

    return env.get_template('page.html.j2').render(
            version          = __version__,
            page_title       = clan_name + "Clan Dashboard",
            update_date      = datetime.now().strftime('%c'),
            content          = member_table,
            clan_name        = clan_name,
            clan_id          = clan_id,
            clan_description = clan_description,
            clan_stats       = clan_stats
        )

def build_dashboard(api_key, clan_id, logo_path, favicon_path, description_path, output_path):
    """Compile and render clan dashboard."""

    # Putting everything in a `try`...`finally` to ensure `tempdir` is removed
    # when we're done. We don't want to pollute the user's disk.
    try:
        # Create temporary directory. All file writes, until the very end,
        # will happen in this directory, so that no matter what we do, it
        # won't hose existing stuff.
        tempdir = tempfile.mkdtemp("traasorg")
        
        log_path = os.path.join(tempdir, 'log')
        os.makedirs(log_path)

        # copy static assets to output path
        shutil.copytree(os.path.join(os.path.dirname(__file__), 'static'), os.path.join(tempdir, 'static'))

        # If logo_path is provided, grab logo from path given, and put it where 
        # it needs to go. Otherwise, grab the default from the static folder
        logo_dest_path = os.path.join(tempdir, 'clan_logo.png')
        if logo_path:
            logo_src_path = os.path.expanduser(logo_path)
            shutil.copyfile(logo_src_path, logo_dest_path)
        else:
            shutil.copyfile(os.path.join(os.path.dirname(__file__), 'static/crtools-logo.png'), logo_dest_path)        

        # If favicon_path is provided, grab favicon from path given, and put it  
        # where it needs to go. Otherwise, grab the default from the static folder
        favicon_dest_path = os.path.join(tempdir, 'favicon.ico')
        if favicon_path:
            favicon_src_path = os.path.expanduser(favicon_path)
            shutil.copyfile(favicon_src_path, favicon_dest_path)
        else:
            shutil.copyfile(os.path.join(os.path.dirname(__file__), 'static/crtools-favicon.ico'), favicon_dest_path)        

        # Get clan data from API. Write to log.
        clan = get_clan(api_key, clan_id)
        write_object_to_file(os.path.join(log_path, 'clan.json'), json.dumps(clan, indent=4))

        clan_description = clan['description']
        if description_path:
            description_path = os.path.expanduser(description_path)
            if os.path.isfile(description_path):
                with open(description_path, 'r') as myfile:
                    clan_description = myfile.read()
            else:
                clan_description = "ERROR: File '{}' does not exist.".format(description_path)

        # Get war log data from API. Write to log.
        warlog = get_warlog(api_key, clan_id)
        write_object_to_file(os.path.join(log_path, 'warlog.json'), json.dumps(warlog, indent=4))

        # grab importent fields from member list for dashboard
        member_dash = []
        for member in clan['memberList']:
            member_row = member
            member_row['warlog'] = member_warlog(member['tag'], warlog)
            member_row['danger'] = member_danger(member, member_row['warlog'])
            if member['role'] == 'leader' or member['role'] == 'coLeader':
                member_row['leadership'] = True
            else: 
                member_row['leadership'] = False
            if member['role'] == 'coLeader':
                member['role'] = 'co-leader'
            member_dash.append(member_row)

        env = Environment(
            loader=PackageLoader('crtools', 'templates'),
            autoescape=select_autoescape(['html', 'xml'])
        )

        template = env.get_template('clan-stats-table.html.j2')
        stats_html = template.render( clan )
        dashboard_html = render_dashboard(env, member_dash, clan['name'], clan['tag'], clan_description, clan['requiredTrophies'], stats_html, warlog_dates(warlog))
        write_object_to_file(os.path.join(tempdir, 'index.html'), dashboard_html)
        
        # remove output directory if previeously created to cleanup. Then 
        # create output path and log path.
        output_path = os.path.expanduser(output_path)
        if os.path.exists(output_path):
            shutil.copystat(output_path, tempdir)
            shutil.rmtree(output_path)

        # Copy entire contents of temp directory to output directory
        shutil.copytree(tempdir, output_path)
    finally:
        # Ensure that temporary directory gets deleted no matter what
        shutil.rmtree(tempdir)

