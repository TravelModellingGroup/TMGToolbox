# ---LICENSE----------------------
#
#     Copyright 2014 Travel Modelling Group, Department of Civil Engineering, University of Toronto
#
#     This file is part of the TMG Toolbox.
#
#     The TMG Toolbox is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     The TMG Toolbox is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with the TMG Toolbox.  If not, see <http://www.gnu.org/licenses/>.
#
# ---METADATA---------------------
#
# build_toolbox.py
#
#     Author: pkucirek
#
#     This script builds a full, unconsolidated MTBX file (EMME Modeller Toolbox), by analyzing
#     the source code from the working directory. It is intended to be run as a standalone script
#     from the Python console. It makes use of the EMMEPATH environment variable to determine the
#     current version of EMME being used (in order to build the correct version of the Toolbox
#     file). EMME is a product of INRO Consultants Inc.
#
#     Usage: build_toolbox.py [-p toolbox_path] [-t toolbox_title] [-n toolbox_namespace] [-s source_folder]
#             [-c]
#
#         [-p toolbox_path]: Optional argument. Specifies the name of the MTBX file. If omitted,
#             defaults to 'TMG_Toolbox.mtbx' inside the working directory.
#
#         [-t toolbox_title]: Optional argument. Specifies the title of the MTBX file, as it will
#             appear in EMME Modeller. If omitted, defaults to 'TMG Toolbox'
#
#         [-n toolbox_namespace]: Optional argument. Specifies the initial namespace of all tools
#             in the toolbox. If omitted, defaults to 'tmg'
#
#         [-s source_folder]: Optional argument. Specifies the location of the source code folder.
#             If omitted, default to 'src' inside of the working directory.
#
#         [-c]: Consolidate toolbox flag (optional argument). If included, the output MTBX file
#             will be 'consolidated' (e.g., instead of referencing the source code files, it will
#             contain the compiled Python code).
#

from __future__ import print_function

import base64
import os
import pickle
import py_compile
import sqlite3.dbapi2 as sqllib
import subprocess
from datetime import datetime

import inro.director.util.ucs as ucslib

CONJUNCTIONS = {'and', 'for', 'or', 'the', 'in', 'at', 'as', 'by', 'so', 'that'}


def capitalize_name(name):
    """Takes a name of the form "V3_line_haul" and converts it to a titled name "V3 Line Haul". Also checks for
    conjunctions to remain lower-case."""
    tokens = name.split('_')
    new_tokens = []
    for token in tokens:
        if token in CONJUNCTIONS:
            new_tokens.append(token)
        else:
            try:
                first_char = token[0]
                remaining = token[1:]
                new_token = first_char.upper() + remaining
                new_tokens.append(new_token)
            except Exception as e:
                print(str(tokens))
                print(str(e))
                exit()

    return ' '.join(new_tokens)


VALID_NAMESPACE_CHARS = set([c for c in 'qwertyuiopasdfghjklzxcvbnm_QWERTYUIOPASDFGHJKLZXCVBNM1234567890'])


def check_namespace(ns):
    """Validates tool namespaces, which can only contain letters, numerals, and the underscore character. Raises an
    error if the namespace is not valid."""

    for c in ns:
        if c not in VALID_NAMESPACE_CHARS:
            raise InvalidNamespaceError("'%s' in '%s'" % (c, ns))


def get_emme_version(return_type=str):
    """Gets the version information out of EMME"""

    temp_env = {'PATH': os.getenv('PATH') + '%s\\programs;' % os.getenv('EMMEPATH')}
    emme_process = subprocess.Popen(['emme', '-V'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=temp_env)
    output = emme_process.communicate()[0].decode('utf-8')
    retval = output.split(',')[0]
    if return_type == str:
        return retval

    components = retval.split(' ')
    version = components[1].split('.')
    version_tuple = [int(n) for n in version]
    if return_type == tuple:
        return version_tuple
    elif return_type == float:
        return version_tuple[0] + version_tuple[1] * 0.1
    elif return_type == int:
        return version_tuple[0]
    else:
        raise TypeError("Type %s not accepted for getting EMME version" % return_type)


class InvalidNamespaceError(Exception):
    pass


# ---CLASS ARCHITECTURE
'''This architecture allows the Toolbox hierarchy to be pre-loaded from the  source folder. Pre-loading the data
simplifies dumping it into the actual MTBX file, which is flat by nature.'''


class ElementTree(object):

    def __init__(self, title, namespace):
        check_namespace(namespace)

        self.begin = str(datetime.now())
        self.next_element_id = 0

        self.element_id = self.next_id()
        self.title = title
        self.namespace = namespace

        self.parent = None
        self.children = []

        # Version is of the form "EMME x.x.x"
        version = get_emme_version(str)
        self.version = "EMME %s" % version

    def next_id(self):
        self.next_element_id += 1
        return self.next_element_id

    def add_folder(self, title, namespace):
        node = FolderNode(self.next_id(), title, namespace)

        node.parent = self
        node.root = self
        self.children.append(node)

        return node

    def add_tool(self, title, namespace, script_path, consolidate):
        try:
            node = ToolNode(self.next_id(), title, namespace, script_path, consolidate)
        except Exception as e:
            print(type(e), str(e))
            return None

        node.parent = self
        node.root = self
        self.children.append(node)

        return node


class FolderNode(object):

    def __init__(self, element_id, title, namespace):
        check_namespace(namespace)

        self.element_id = element_id
        self.title = title
        self.namespace = namespace

        self.parent = None
        self.root = None
        self.children = []

    def add_folder(self, title, namespace):
        node = FolderNode(self.root.next_id(), title, namespace)
        node.parent = self
        node.root = self.root
        self.children.append(node)

        return node

    def add_tool(self, title, namespace, script_path, consolidate):
        try:
            node = ToolNode(self.root.next_id(), title, namespace, script_path, consolidate)
        except Exception as e:
            print(type(e), str(e))
            return None

        node.parent = self
        node.root = self.root
        self.children.append(node)

        return node


class ToolNode(object):

    def __init__(self, element_id, title, namespace, script_path, consolidate):
        check_namespace(namespace)

        self.element_id = element_id
        self.title = title
        self.namespace = namespace

        self.parent = None
        self.root = None

        script_path_py = script_path + '.py'

        if consolidate:
            self.script = ''
            self.extension = '.pyc'

            script_path_pyc = script_path + '.pyc'
            py_compile.compile(script_path_py, cfile=script_path_pyc)
            with open(script_path_pyc, 'rb') as reader:
                compiled_binary = reader.read()
            os.remove(script_path_pyc)
            code = base64.b64encode(pickle.dumps(compiled_binary))
            self.code = ucslib.transform(code)

        else:
            self.script = script_path_py
            self.code = ''
            self.extension = '.py'


class MTBXDatabase(object):
    """Handles the lower-level creation of the MTBX file.

    This is a stand-in, pending the creation of an official API for INRO's MTBX format. With any luck, the architecture
    put together in ElementTree is sufficiently flexible going forward."""

    FORMAT_MAGIC_NUMBER = 'B8C224F6_7C94_4E6F_8C2C_5CC06F145271'
    TOOLBOX_MAGIC_NUMBER = 'TOOLBOX_C6809332_CD61_45B3_9060_411D825669F8'
    CATEGORY_MAGIC_NUMBER = 'CATEGORY_984876A0_3350_4374_B47C_6D9C5A47BBC8'
    TOOL_MAGIC_NUMBER = 'TOOL_1AC06B56_6A54_431A_9515_0BF77013646F'

    def __init__(self, fp, title):
        if os.path.exists(fp):  # Remove the file if it already exists
            # Check if the MTBX file is in use by EMME
            check_file = '%s-wal' % fp
            if os.path.exists(check_file):
                raise RuntimeError('`%s` is currently in use by EMME. Please close EMME before running this script.' % fp)
            os.remove(fp)

        self.db = sqllib.connect(fp)

        self._create_attribute_table()
        self._create_element_table()
        self._create_document_table()
        self._create_triggers()

        self._initialize_documents_table(title)

    def _create_attribute_table(self):
        sql = """CREATE TABLE attributes(
            element_id INTEGER REFERENCES elements(element_id),
            name VARCHAR,
            value VARCHAR,
            PRIMARY KEY(element_id, name));"""

        self.db.execute(sql)

    def _create_element_table(self):
        sql = """CREATE TABLE elements(
            element_id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER REFERENCES elements(element_id),
            document_id INTEGER REFERENCES documents(document_id),
            tag VARCHAR,
            text VARCHAR,
            tail VARCHAR);"""

        self.db.execute(sql)

    def _create_document_table(self):
        sql = """CREATE TABLE documents(
            document_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title VARCHAR);"""

        self.db.execute(sql)

    def _create_triggers(self):
        sql = """CREATE TRIGGER documents_delete
            BEFORE DELETE on documents
            FOR EACH ROW BEGIN
                DELETE FROM elements WHERE document_id = OLD.document_id;
            END"""

        self.db.execute(sql)

        sql = """CREATE TRIGGER elements_delete
            BEFORE DELETE on elements
            FOR EACH ROW BEGIN
                DELETE FROM attributes WHERE element_id = OLD.element_id;
            END"""

        self.db.execute(sql)

    def _initialize_documents_table(self, title):
        sql = """INSERT INTO documents (document_id, title)
                VALUES (1, '%s');""" % title

        self.db.execute(sql)
        self.db.commit()

    def populate_tables_from_tree(self, tree):
        # Insert into the elements table
        column_string = "element_id, document_id, tag, text, tail"
        value_string = "{id}, 1, '{title}', '', ''".format(id=tree.element_id, title=tree.title)
        sql = """INSERT INTO elements (%s)
                VALUES (%s);""" % (column_string, value_string)
        self.db.execute(sql)

        # Insert into the attributes table
        column_string = "element_id, name, value"
        atts = {
            'major': '',
            'format': MTBXDatabase.FORMAT_MAGIC_NUMBER,
            'begin': tree.begin,
            'version': tree.version,
            'maintenance': '',
            'minor': '',
            'name': tree.title,
            'description': '',
            'namespace': tree.namespace,
            MTBXDatabase.TOOLBOX_MAGIC_NUMBER: 'True'
        }
        for key, val in atts.items():
            value_string = "{id}, '{name}', '{value}'".format(id=tree.element_id, name=key, value=val)
            sql = """INSERT INTO attributes (%s)
                    VALUES (%s);""" % (column_string, value_string)
            try:
                self.db.execute(sql)
            except Exception as e:
                print(sql)
                print(str(e))
                exit()

        self.db.commit()

        # Handle children nodes
        for child in tree.children:
            if isinstance(child, ToolNode):
                self._insert_tool(child)
            else:
                self._insert_folder(child)

    def _insert_folder(self, node):
        # Insert into the elements table
        column_string = "element_id, parent_id, document_id, tag, text, tail"
        value_string = "{id}, {parent}, 1, '{title}', '', ''".format(id=node.element_id, parent=node.parent.element_id,
                                                                     title=node.title)
        sql = """INSERT INTO elements (%s)
                VALUES (%s);""" % (column_string, value_string)
        self.db.execute(sql)

        # Insert into the attributes table
        column_string = "element_id, name, value"
        atts = {
            'namespace': node.namespace,
            'description': '',
            'name': node.title,
            'children': [c.element_id for c in node.children],
            MTBXDatabase.CATEGORY_MAGIC_NUMBER: 'True'
        }
        for key, val in atts.items():
            value_string = "{id}, '{name}', '{value}'".format(id=node.element_id, name=key, value=val)
            sql = """INSERT INTO attributes (%s)
                    VALUES (%s);""" % (column_string, value_string)
            self.db.execute(sql)

        self.db.commit()

        # Handle children nodes
        for child in node.children:
            if isinstance(child, ToolNode):
                self._insert_tool(child)
            else:
                self._insert_folder(child)

    def _insert_tool(self, node):
        # Insert into the elements table
        column_string = "element_id, parent_id, document_id, tag, text, tail"
        value_string = "{id}, {parent}, 1, '{title}', '', ''".format(id=node.element_id, parent=node.parent.element_id,
                                                                     title=node.title)
        sql = """INSERT INTO elements (%s)
                VALUES (%s);""" % (column_string, value_string)
        self.db.execute(sql)

        # Insert into the attributes table
        column_string = "element_id, name, value"
        atts = {
            'code': node.code,
            'description': '',
            'script': node.script,
            'namespace': node.namespace,
            'python_suffix': node.extension,
            'name': node.title,
            MTBXDatabase.TOOL_MAGIC_NUMBER: 'True'
        }
        for key, val in atts.items():
            value_string = "{id}, '{name}', '{value!s}'".format(id=node.element_id, name=key, value=val)
            sql = """INSERT INTO attributes (%s)
                    VALUES (?, ?, ?);""" % column_string
            self.db.execute(sql, (node.element_id, key, val))

        self.db.commit()


# ---MAIN METHOD

def build_toolbox(fp, source, title='TMG Toolbox', namespace='tmg', consolidate=False):
    print("------------------------")
    print(" Build Toolbox Utility")
    print("------------------------\n")
    print("toolbox: %s" % fp)
    print("source folder: %s" % source)
    print("title: %s" % title)
    print("namespace: %s" % namespace)
    print("consolidate: %s" % consolidate)

    print("\nLoading toolbox structure")
    tree = ElementTree(title, namespace)
    explore_source_folder(source, tree, consolidate)
    print("Done! Found %s elements." % tree.next_element_id)

    print("\nBuilding MTBX file...")
    mtbx = MTBXDatabase(fp, title)
    mtbx.populate_tables_from_tree(tree)
    print("Done!")


def explore_source_folder(root_folder_path, parent_node, consolidate):
    """Recursive function for building the pseudo-Toolbox structure"""
    folders = []
    files = []
    for item in os.listdir(root_folder_path):
        item_path = os.path.join(root_folder_path, item)
        if os.path.isfile(item_path):
            name, extension = os.path.splitext(item)
            if extension == '.py':
                files.append(name)
        else:
            folders.append(item)

    for folder in folders:
        if folder in ['.vs', '.idea', '.vscode', '.git', '__pycache__']:
            continue
        folder_path = os.path.join(root_folder_path, folder)
        namespace = folder
        title = capitalize_name(namespace)

        folder_node = parent_node.add_folder(title, namespace)
        explore_source_folder(folder_path, folder_node, consolidate)

    for file in files:
        namespace = file
        title = capitalize_name(namespace)
        script_path = os.path.join(root_folder_path, file)
        parent_node.add_tool(title, namespace, script_path, consolidate)


if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--path', help="Output file path. Default is 'TMG_Toolbox.mtbs' in the working folder.")
    parser.add_argument('-t', '--title', help="Title of the Toolbox. Default is 'TMG Toolbox'")
    parser.add_argument('-n', '--namespace', help="The initial namespace. Default is 'tmg'")
    parser.add_argument('-s', '--src', help="Path to the source code folder. Default is 'src' in the working folder.")
    parser.add_argument('-c', '--consolidate',
                        help="Flag indicating if the output toolbox is to be consolidated (compiled).",
                        action='store_true')

    args = parser.parse_args()

    current_folder = os.path.dirname(os.path.abspath(__file__))
    src_folder = os.path.join(current_folder, 'src') if args.src is None else args.src
    toolbox_title = "TMG Toolbox" if args.title is None else args.title
    toolbox_fp = os.path.join(current_folder, 'TMG_Toolbox.mtbx') if args.path is None else args.path
    toolbox_namespace = 'tmg' if args.namespace is None else args.namespace
    consolidate_flag = args.consolidate

    build_toolbox(toolbox_fp, src_folder, toolbox_title, toolbox_namespace, consolidate_flag)
