#!/usr/bin/env python
# Copyright 2019 The Fuchsia Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import defaultdict
import os
import sys

GOLDENS_TMPL = """
// Autogenerated: Do not modify!
#include <map>
#include <string>
#include <utility>
#include <vector>
#include "goldens.h"

std::map<std::string, std::vector<std::string>> Goldens::dep_order_ = {{
{dep_order}
}};

std::map<std::string, std::string> Goldens::json_ = {{
{json}
}};

std::map<std::string, std::string> Goldens::tables_ = {{
{tables}
}};

std::map<std::string, std::string> Goldens::fidl_ = {{
{fidl}
}};
"""


def get_testname(filename):
    """
    Return a standardized test name given a filename corresponding to a golden
    JSON file, a coding tables file, a fidl file, or an order.txt file.
    >>> get_testname('foo/bar/testdata/mytest/order.txt')
    'mytest'
    >>> get_testname('foo/bar/goldens/mytest.test.json.golden')
    'mytest'
    >>> get_testname('foo/bar/goldens/mytest.test.tables.c.golden')
    'mytest'
    >>> get_testname('foo/bar/testdata/mytest.test.fidl')
    'mytest'
    """
    path = filename.split('/')
    dirname = 'goldens' if '/goldens/' in filename else 'testdata'
    dir_index = path.index(dirname)
    return path[dir_index + 1].split('.')[0]


def format_list(l):
    """ Format a python list as a c++ vector
    >>> format_list(['a', 'b'])
    '{"a", "b"}'
    """
    return '{{{0}}}'.format(', '.join(map(format_str, l)))


def format_str(s, delimiter=None):
    """ Format a python str as a c++ string literal. """
    if not delimiter:
        return '"{0}"'.format(s)
    return 'R"{delim}({s}){delim}"'.format(s=s, delim=delimiter)


def get_goldens_cc(inputs):
    # group the filenames by test, for each test, we keep track of:
    # the json for that test, the coding tables for that test,
    # the list of FIDL files, their dependency order,
    # and the contents of those FIDL files.
    testname_to_order = {}
    testname_to_fidl_files = defaultdict(list)
    json_testname_to_golden = {}
    tables_testname_to_golden = {}
    fidl_file_contents = {}
    for filename in inputs:
        testname = get_testname(filename)
        if filename.endswith('order.txt'):
            testname_to_order[testname] = open(filename, 'r').read().split()
        elif '/goldens/' in filename:
            if filename.endswith('.json.golden'):
                json_testname_to_golden[testname] = open(filename, 'r').read()
            elif filename.endswith('.tables.c.golden'):
                tables_testname_to_golden[testname] = open(filename, 'r').read()
        elif '/testdata/' in filename:
            name = os.path.basename(filename)
            file_key = testname + '/' + name
            testname_to_fidl_files[testname].append(file_key)
            fidl_file_contents[file_key] = open(filename, 'r').read()
        else:
            raise RuntimeError('Unknown path: ' + filename)
    # each test has exactly one golden, and at least one fidl file, so the
    # keys for these two dicts should contain the exact same test names
    goldens = set(json_testname_to_golden.keys()).union(set(tables_testname_to_golden.keys()))
    missing_goldens = goldens - set(testname_to_fidl_files.keys())
    assert len(missing_goldens) == 0, missing_goldens
    missing_fidls = set(testname_to_fidl_files.keys()) - goldens
    assert len(missing_fidls) == 0, missing_fidls

    # sort the list of FIDL files per test by dependency order
    for testname, order in testname_to_order.items():
        testname_to_fidl_files[testname].sort(
            key=lambda p: order.index(os.path.basename(p)))

    # output C++ file
    dep_order = []
    json = []
    tables = []
    fidl = []
    for testname in testname_to_fidl_files:
        dep_order.append(
            '\t{{{0}, {1}}},'.format(
                format_str(testname),
                format_list(testname_to_fidl_files[testname])))
    for testname in json_testname_to_golden:
        json.append(
            '\t{{{0}, {1}}},'.format(
                format_str(testname),
                format_str(json_testname_to_golden[testname], delimiter='JSON')))
    for testname in tables_testname_to_golden:
        tables.append(
            '\t{{{0}, {1}}},'.format(
                format_str(testname),
                format_str(tables_testname_to_golden[testname], delimiter='C')))
    for filename, contents in fidl_file_contents.items():
        fidl.append(
            '\t{{{0}, {1}}},'.format(
                format_str(filename), format_str(contents, delimiter='FIDL')))
    return GOLDENS_TMPL.format(
        dep_order='\n'.join(dep_order),
        json='\n'.join(json),
        tables='\n'.join(tables),
        fidl='\n'.join(fidl))


if __name__ == '__main__':
    goldens = get_goldens_cc(sys.argv[2:])
    with open(sys.argv[1], 'w') as f:
        f.write(goldens)
