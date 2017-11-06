#!/usr/bin/env python3
# -*- coding: utf-8 -*-

## Copyright (C) 2016 Bitergia
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
##
## Authors:
##   Jesus M. Gonzalez-Barahona <jgb@bitergia.com>
##

import argparse
import json
import logging
from pprint import pprint
import sys

from xlrd import open_workbook

description = """Create a projects.json file from a spreadsheet.

Reads data from an Excel spreadsheet, "Mozilla format"

Example:
    spreadsheet_to_projects --spreadsheet projects.xlsx --json projects.json

"""

def parse_args ():

    parser = argparse.ArgumentParser(description = description)
    parser.add_argument("-l", "--logging", type=str, choices=["info", "debug"],
                        help = "Logging level for output")
    parser.add_argument("--logfile", type=str,
                            help = "Log file")
    parser.add_argument("--spreadsheet", type=str, required=True,
                        help = "Excel file with projects data")
    parser.add_argument("--json", type=str, required=True,
                        help = "Name of projects.json file")
    parser.add_argument("--show_projects",
                        action="store_true",
                        help = "Show found projects")

    args = parser.parse_args()
    return args


class Sheet ():
    """Deal with sheets (generic code).

    First line: headers (usually, just ignore)

    """

    def __init__(self, sheet):
        """Constructor

        :param sheet: sheet in the spreadsheet

        """

        logging.debug("Sheet: " + sheet.name)
        # Name of the sheet
        self.sheet = sheet
        # Dictionary for repos (key is project, value number of
        # repos_projects)
        self.repos = {}
        # Dictionary for projects (key is repo, value is project)
        self.projects = {}
        # Defaults for colummnos in spreadsheet
        self._init_columns()

    def _init_columns(self):

        self.repo_columns = [0]
        self.project_column = 1

    def _get_repo(self, row):
        """Get repo from row in spreadsheet.

        """

        return self.sheet.cell(row,self.repo_columns[0]).value

    def _normalize_repo(self, repo):
        """Normalize repository name.

        By default, nothing to do.

        """

        return repo

    def get_repos(self, show_projects=False):
        """Get dictionary with repos pointing to their projects.

        """

        # Read all rows with data in spreadsheet (skip header)
        for row in range(1,self.sheet.nrows):
            repo = self._get_repo(row)
            repo = self._normalize_repo(repo)
            project = self.sheet.cell(row,self.project_column).value
            logging.info("Found in spreadsheet: {}, {}".format(repo, project))
            if project == '':
                project = 'Unknown'
            self.projects[repo] = project
            if project in self.repos:
                self.repos[project] += 1
            else:
                self.repos[project] = 1
        if show_projects:
            print("Analyzed sheet " + self.sheet.name)
            print("Repos found in spreadsheet (per project)")
            for project in sorted(self.repos.keys()):
                print("Project:", project, "repos: ",
                    self.repos[project])
        return self.projects

def normalized_ghrepo(repo):
    """Normalize names of HitHub repos.

    'http://' is changed to 'https://'
    Uppercase is changed to lowercase

    :param repo: repo to normalize

    """

    normalized = repo.replace('https://','http://',1)
    normalized = normalized.lower()
    return normalized

def normalized_bzrepo(url, product, component):
    """Normalize names of Bugzilla repos.

    Repos come as product, component.
    Concatenate both, separated by '/'

    :param       url: url to normalize
    :param   product: product to normalize
    :param component: component to normalize

    """

    normalized = url + '/bugs/buglist.cgi?' \
        'product='+ product.replace(' ','+') + \
        '&component=' + component.replace(' ','+')
    return normalized

class GitHubSheet (Sheet):
    """Deal with GitHub sheet.

    First column: GitHub repo (full url)
    Second column: project

    """

    pass

class BugzillaSheet (Sheet):
    """Deal with Bugzilla sheet.

    Second column: product
    Third column: Component
    Fourth column: project

    """

    def _init_columns(self):

        self.repo_columns = [0,1,2]
        self.project_column = 3

    def _get_repo(self, row):
        """Get repo from row in spreadsheet.

        """

        url = self.sheet.cell(row,self.repo_columns[0]).value
        product = self.sheet.cell(row,self.repo_columns[1]).value
        component = self.sheet.cell(row,self.repo_columns[2]).value
        return normalized_bzrepo(url, product, component)

class EmailSheet (Sheet):
    """Deal with Email sheet.

    First column: Email list name
    Second column: project

    """

    def _normalize_repo(self, repo):
        """Normalize repository name.

        We need a string like 'news.mozilla.org mozilla.addons.chromebug'
        """
        if (repo.rfind('news.mozilla.org-') == 0):
            repo = repo.replace('news.mozilla.org-','news.mozilla.org ')
        return repo

class DiscourseSheet (Sheet):
    """Deal with Email sheet.

    First column: Category
    Third column: project

    """

    def _init_columns(self):

        self.repo_columns = [1]
        self.project_column = 2

    def _normalize_repo(self, repo):

        return str(int(repo))

class StackOverflow(Sheet):
    """ StackOverflow data

    First column: tag
    Second column: project
    """
    url = "http://stackoverflow.com/questions/tagged/"

    def _normalize_repo(self, repo):
        return str( self.url + repo)

class Meetup (Sheet):
    """Deal with Meetup sheet.

    First column: Meetup ID (name with hyphens)
    Second column: project

    """

class IRC(Sheet):
    """ IRC data

    First column: channel in irc.mozilla.org
    Second column: project
    """

    def _normalize_repo(self, repo):

        supybot_repo = "irc://irc.mozilla.org/%s /home/bitergia/irc/percevalbot/logs/ChannelLogger/mozilla/#%s" % (repo, repo)
        return supybot_repo


def add_adhoc_repositories(projects_tree, spreadsheet):
    """
    Add the needed adhoc repositories for data sources which need extra
    information using the `Unknown` project.

    E.g.: Data sources like Discourse just provide a category number per project.
    The projects.json file needs the endpoint for Discourse under the
    project name `unknown`.

    WARNING: `unknown` as it is written in lowercase won't be used in enrichment phase
    """
    def __init_unknown_project(tree):
        if 'unknown' not in tree.keys():
            tree['unknown'] = {}
        return tree

    projects_tree = __init_unknown_project(projects_tree)
    projects_tree['unknown']['bugzillarest'] = ["https://bugzilla.mozilla.org"]
    projects_tree['unknown']['discourse'] = ["https://discourse.mozilla.org/"]
    projects_tree['unknown']['mediawiki'] = ["https://wiki.mozilla.org"]
    projects_tree['unknown']['mozillaclub'] = ["https://spreadsheets.google.com/feeds/cells/1QHl2bjBhMslyFzR5XXPzMLdzzx7oeSKTbgR5PM8qp64/ohaibtm/public/values?alt=json"]
    projects_tree['unknown']['remo'] = ["https://reps.mozilla.org"]

    return projects_tree


def main():
    args = parse_args()
    if args.logging:
        log_format = '%(levelname)s:%(message)s'
        if args.logging == "info":
            level = logging.INFO
        elif args.logging == "debug":
            level = logging.DEBUG
        if args.logfile:
            logging.basicConfig(format=log_format, level=level,
                                filename = args.logfile, filemode = "w")
        else:
            logging.basicConfig(format=log_format, level=level)

    wb = open_workbook(args.spreadsheet)
    projects = {}

    spreadsheet = {}
    for sheet in wb.sheets():
        if (sheet.name == 'Github'):
            sheet_obj = GitHubSheet(sheet)
            spreadsheet['github'] = sheet_obj.get_repos(
                    show_projects = args.show_projects)
            spreadsheet['git'] = {}
            for repo, project in spreadsheet['github'].items():
                spreadsheet['git'][repo+'.git'] = project
        elif (sheet.name == "Bugzilla"):
            sheet_obj = BugzillaSheet(sheet)
            spreadsheet['bugzilla'] = sheet_obj.get_repos(
                    show_projects = args.show_projects)
        elif (sheet.name == "Mailing lists"):
            sheet_obj = EmailSheet(sheet)
            spreadsheet['nntp'] = sheet_obj.get_repos(
                    show_projects = args.show_projects)
        elif (sheet.name == "Discourse"):
            sheet_obj = DiscourseSheet(sheet)
            spreadsheet['discourse'] = sheet_obj.get_repos(
                    show_projects = args.show_projects)
        elif (sheet.name == "StackOverflow"):
            sheet_obj = StackOverflow(sheet)
            spreadsheet['stackexchange'] = sheet_obj.get_repos(
                    show_projects = args.show_projects)
        elif (sheet.name == "Meetup"):
            sheet_obj = Meetup(sheet)
            spreadsheet['meetup'] = sheet_obj.get_repos(
                    show_projects = args.show_projects)
        elif (sheet.name == "IRC"):
            sheet_obj = IRC(sheet)
            spreadsheet['supybot'] = sheet_obj.get_repos(
                    show_projects = args.show_projects)

    for datasource in spreadsheet:
        for repo, project in spreadsheet[datasource].items():
            if project not in projects:
                projects[project] = {}
            if datasource not in projects[project]:
                projects[project][datasource] = set()
            projects[project][datasource].add(repo)

    for project in projects:
        for datasource in projects[project]:
            projects[project][datasource] = sorted(projects[project][datasource])
        if 'meta' not in projects[project]:
            projects[project]['meta'] = project.lower()

    projects = add_adhoc_repositories(projects, spreadsheet)

    with open(args.json, 'w') as json_fp:
        json.dump(projects, json_fp, sort_keys=True, indent=4)

if __name__ == "__main__":
    main()
