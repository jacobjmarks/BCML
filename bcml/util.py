# pylint: disable=missing-docstring
# Copyright 2019 Nicene Nerd <macadamiadaze@gmail.com>
# Licensed under GPLv3+
import csv
from dataclasses import dataclass
import json
import os
import re
import shutil
import subprocess
import sys
import traceback
import unicodedata
import urllib.error
import urllib.request
from collections import namedtuple, OrderedDict
from collections.abc import Mapping
from configparser import ConfigParser
from pathlib import Path
from typing import Union, List

import byml
from byml import yaml_util
import sarc
import syaz0
import xxhash
from webview import Window
import yaml


CREATE_NO_WINDOW = 0x08000000
SARC_EXTS = {'.sarc', '.pack', '.bactorpack', '.bmodelsh', '.beventpack', '.stera', '.stats',
             '.ssarc', '.spack', '.sbactorpack', '.sbmodelsh', '.sbeventpack', '.sstera', '.sstats'}
AAMP_EXTS = {'.bxml', '.sbxml', '.bas', '.sbas', '.baglblm', '.sbaglblm', '.baglccr', '.sbaglccr',
             '.baglclwd', '.sbaglclwd', '.baglcube', '.sbaglcube', '.bagldof', '.sbagldof',
             '.baglenv', '.sbaglenv', '.baglenvset', '.sbaglenvset', '.baglfila', '.sbaglfila',
             '.bagllmap', '.sbagllmap', '.bagllref', '.sbagllref', '.baglmf', '.sbaglmf',
             '.baglshpp', '.sbaglshpp', '.baiprog', '.sbaiprog', '.baslist', '.sbaslist',
             '.bassetting', '.sbassetting', '.batcl', '.sbatcl', '.batcllist', '.sbatcllist',
             '.bawareness', '.sbawareness', '.bawntable', '.sbawntable', '.bbonectrl',
             '.sbbonectrl', '.bchemical', '.sbchemical', '.bchmres', '.sbchmres', '.bdemo',
             '.sbdemo', '.bdgnenv', '.sbdgnenv', '.bdmgparam', '.sbdmgparam', '.bdrop', '.sbdrop',
             '.bgapkginfo', '.sbgapkginfo', '.bgapkglist', '.sbgapkglist', '.bgenv', '.sbgenv',
             '.bglght', '.sbglght', '.bgmsconf', '.sbgmsconf', '.bgparamlist', '.sbgparamlist',
             '.bgsdw', '.sbgsdw', '.bksky', '.sbksky', '.blifecondition', '.sblifecondition',
             '.blod', '.sblod', '.bmodellist', '.sbmodellist', '.bmscdef', '.sbmscdef', '.bmscinfo',
             '.sbmscinfo', '.bnetfp', '.sbnetfp', '.bphyscharcon', '.sbphyscharcon',
             '.bphyscontact', '.sbphyscontact', '.bphysics', '.sbphysics', '.bphyslayer',
             '.sbphyslayer', '.bphysmaterial', '.sbphysmaterial', '.bphyssb', '.sbphyssb',
             '.bphyssubmat', '.sbphyssubmat', '.bptclconf', '.sbptclconf', '.brecipe', '.sbrecipe',
             '.brgbw', '.sbrgbw', '.brgcon', '.sbrgcon', '.brgconfig', '.sbrgconfig',
             '.brgconfiglist', '.sbrgconfiglist', '.bsfbt', '.sbsfbt', '.bsft', '.sbsft', '.bshop',
             '.sbshop', '.bumii', '.sbumii', '.bvege', '.sbvege', '.bactcapt', '.sbactcapt'}
BYML_EXTS = {'.bgdata', '.sbgdata', '.bquestpack', '.sbquestpack', '.byml', '.sbyml', '.mubin',
             '.smubin', '.baischedule', '.sbaischedule', '.baniminfo', '.sbaniminfo', '.bgsvdata',
             '.sbgsvdata'}


class BcmlMod:
    priority: int
    path: Path

    def __init__(self, mod_path):
        self.path = mod_path
        self._info = json.loads(
            (self.path / 'info.json').read_text('utf-8'),
            encoding='utf-8'
        )
        self.priority = self._info['priority']

    def __repr__(self):
        return f"""BcmlMod(name="{
            self.name
        }", path="{
            self.path.as_posix()
        }", priority={self.priority})"""

    def __hash__(self):
        return hash(str(self))

    def __eq__(self, other):
        return hash(self) == hash(other)

    def to_json(self) -> dict:
        return {
            'name': self.name,
            'priority': self.priority,
            'path': str(self.path),
            'disabled': (self.path / '.disabled').exists()
        }

    @staticmethod
    def from_json(json: dict):
        return BcmlMod(Path(json['path']))

    @staticmethod
    def from_info(info_path: Path):
        return BcmlMod(info_path.parent)

    @property
    def name(self) -> str:
        return self._info['name']

    @property
    def id(self) -> str:
        return self._info['id']

    @property
    def description(self) -> str:
        return self._info['description']

    @property
    def image(self) -> str:
        return self._info['image']

    @property
    def url(self) -> str:
        return self._info['url']

    @property
    def dependencies(self) -> List[str]:
        return self._info['depedencies']

    @property
    def info_path(self):
        return self.path / 'info.json'

    @property
    def disabled(self):
        return (self.path / '.disabled').exists()

    def _get_folder_id(self):
        return f'{self.priority}_' + re.sub(
            r'(?u)[^-\w.]', '', self.name.strip().replace(' ', '')
        )

    def _save_changes(self):
        self.info_path.write_text(
            json.dumps(self._info, ensure_ascii=False),
            encoding='utf-8'
        )

    @property
    def mergers(self) -> list:
        from .mergers import get_mergers_for_mod
        return get_mergers_for_mod(self)

    def get_partials(self) -> dict:
        partials = {}
        for m in self.mergers:
            if m.can_partial_remerge():
                partials[m.NAME] = m.get_mod_affected(self)
        return partials


    def change_priority(self, priority):
        self.priority = priority
        self._info['priority'] = priority
        self._save_changes()
        self.path.rename(
            self.path.parent.resolve() / self._get_folder_id()
        )

    def get_preview(self) -> Path:
        try:
            return self._preview
        except AttributeError:
            if not list(self.path.glob('thumbnail.*')):
                if self.image:
                    if self.url and 'gamebanana.com' in self.url:
                        response = urllib.request.urlopen(self.url)
                        rdata = response.read().decode()
                        img_match = re.search(
                            r'<meta property=\"og:image\" ?content=\"(.+?)\" />', rdata)
                        if img_match:
                            image_path = 'thumbnail.jfif'
                            urllib.request.urlretrieve(
                                img_match.group(1),
                                str(self.path / image_path)
                            )
                        else:
                            raise IndexError(
                                f'Rule for {self.url} failed to find the remote preview'
                            )
                    else:
                        raise KeyError(f'No preview image available')
                else:
                    image_path = self.image
                    if image_path.startswith('http'):
                        urllib.request.urlretrieve(
                            image_path,
                            str(self.path / ('thumbnail.' + image_path.split(".")[-1]))
                        )
                        image_path = 'thumbnail.' + image_path.split(".")[-1]
                    if not os.path.isfile(str(self.path / image_path)):
                        raise FileNotFoundError(
                            f'Preview {image_path} specified in rules.txt not found')
            else:
                for thumb in self.path.glob('thumbnail.*'):
                    image_path = thumb
            self._preview = self.path / image_path
            return self._preview

        def uninstall(self, wait_merge: bool = False):
            from bcml.install import uninstall_mod
            uninstall_mod(self, wait_merge)


decompress = syaz0.decompress
compress = syaz0.compress


def vprint(content):
    if not isinstance(content, str):
        try:
            content = json.dumps(content, ensure_ascii=False, indent=4)
        except TypeError:
            from . import json_util
            try:
                content = json_util.aamp_to_json(content, pretty=True)
            except TypeError:
                try:
                    content = json_util.byml_to_json(content, pretty=True)
                except TypeError:
                    from pprint import pformat
                    content = pformat(content, compact=True, indent=4)
    print(f'VERBOSE{content}')


def timed(func):
    def timed_function(*args, **kwargs):
        from time import time_ns
        start = time_ns()
        res = func(*args, **kwargs)
        vprint(f'{func.__qualname__} took {(time_ns() - start) / 1000000000} seconds')
        return res
    return timed_function


def get_exec_dir() -> Path:
    """ Gets the root BCML directory """
    return Path(os.path.dirname(os.path.realpath(__file__)))


def get_data_dir() -> Path:
    import platform
    if platform.system() == 'Windows':
        data_dir = Path(os.path.expandvars('%LOCALAPPDATA%')) / 'bcml'
    else:
        data_dir = Path.home() / '.config' / 'bcml'
    if not data_dir.exists():
        data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_work_dir() -> Path:
    """ Gets the BCML internal working directory """
    work_dir = get_data_dir() / 'work_dir'
    if not work_dir.exists():
        work_dir.mkdir(parents=True, exist_ok=True)
    return work_dir


def clear_temp_dir():
    """Empties BCML's temp directories"""
    for path in get_work_dir().glob('tmp*'):
        try:
            if path.is_dir():
                shutil.rmtree(str(path))
            elif path.is_file():
                path.unlink()
        except OSError:
            pass


def get_settings(name: str = '') -> {}:
    try:    
        if not hasattr(get_settings, 'settings'):
            settings = {}
            settings_path = get_data_dir() / 'settings.json'
            if not settings_path.exists():
                settings = {
                    'cemu_dir': '',
                    'game_dir': '',
                    'update_dir': '',
                    'dlc_dir': '',
                    'load_reverse': False,
                    'site_meta': '',
                    'dark_theme': False,
                    'guess_merge': False,
                    'lang': '',
                    'no_cemu': False,
                    'wiiu': True
                }
                with settings_path.open('w', encoding='utf-8') as s_file:
                    json.dump(settings, s_file)
            else:
                settings = json.loads(settings_path.read_text())
            get_settings.settings = settings
        if name:
            return get_settings.settings.get(name, False)
        return get_settings.settings
    except Exception as e:
        e.message = f"""Oops, BCML could not load its settings file. The error: {
            getattr(e, 'message', '')
        }"""
        raise e


def save_settings():
    """Saves changes made to settings"""
    with (get_data_dir() / 'settings.json').open('w', encoding='utf-8') as s_file:
        json.dump(get_settings.settings, s_file)


def get_cemu_dir() -> Path:
    """ Gets the saved Cemu installation directory """
    cemu_dir = str(get_settings('cemu_dir'))
    if not cemu_dir or not Path(cemu_dir).is_dir():
        err = FileNotFoundError('The Cemu directory has moved or not been saved yet.')
        err.error_text = 'The Cemu directory has moved or not been saved yet.'
        raise err
    return Path(cemu_dir)


def set_cemu_dir(path: Path):
    """ Sets the saved Cemu installation directory """
    settings = get_settings()
    settings['cemu_dir'] = str(path.resolve())
    save_settings()


def get_game_dir() -> Path:
    """ Gets the saved Breath of the Wild game directory """
    game_dir = str(get_settings('game_dir'))
    if not game_dir or not Path(game_dir).is_dir():
        err = FileNotFoundError('The BotW game directory has has moved or not been saved yet.')
        err.error_text = 'The BotW game directory has has moved or not been saved yet.'
        raise err
    else:
        return Path(game_dir)


def set_game_dir(path: Path):
    """ Sets the saved Breath of the Wild game directory """
    settings = get_settings()
    settings['game_dir'] = str(path.resolve())
    save_settings()
    try:
        get_mlc_dir()
    except FileNotFoundError:
        try:
            from xml.dom import minidom
            set_path = get_cemu_dir() / 'settings.xml'
            if not set_path.exists():
                err = FileNotFoundError('The Cemu settings file could not be found.')
                err.error_text = 'The Cemu settings file could not be found. This usually means your Cemu directory '\
                                 'is set incorrectly.'
                raise err
            set_read = ''
            with set_path.open('r') as setfile:
                for line in setfile:
                    set_read += line.strip()
            settings = minidom.parseString(set_read)
            mlc_path = Path(settings.getElementsByTagName('mlc_path')[0].firstChild.nodeValue)
        except (FileNotFoundError, IndexError, ValueError, AttributeError):
            mlc_path = get_cemu_dir() / 'mlc01'
        if mlc_path.exists():
            set_mlc_dir(mlc_path)
        else:
            raise FileNotFoundError('The MLC directory could not be automatically located.')


def get_mlc_dir() -> Path:
    """ Gets the saved Cemu mlc directory """
    mlc_dir = str(get_settings('mlc_dir'))
    if not mlc_dir or not Path(mlc_dir).is_dir():
        err = FileNotFoundError('The Cemu MLC directory has moved or not been saved yet.')
        err.error_text = 'The Cemu MLC directory has moved or not been saved yet.'
        raise err
    return Path(mlc_dir)


def set_mlc_dir(path: Path):
    """ Sets the saved Cemu mlc directory """
    settings = get_settings()
    settings['mlc_dir'] = str(path.resolve())
    save_settings()
    if hasattr(get_update_dir, 'update_dir'):
        del get_update_dir.update_dir
    if hasattr(get_aoc_dir, 'aoc_dir'):
        del get_aoc_dir.aoc_dir


def set_site_meta(site_meta):
    """ Caches site meta from url's specified in mods rules.txt """
    settings = get_settings()
    if not 'site_meta' in settings:
        settings['site_meta'] = ''
    else:
        settings['site_meta'] = str(settings['site_meta'] + f'{site_meta};')
    save_settings()


def get_title_id(game_dir: Path = None) -> (str, str):
    """Gets the title ID of the BotW game dump"""
    if not hasattr(get_title_id, 'title_id'):
        title_id = '00050000101C9400'
        if not game_dir:
            game_dir = get_game_dir()
        with (game_dir.parent / 'code' / 'app.xml').open('r') as a_file:
            for line in a_file:
                title_match = re.search(
                    r'<title_id type=\"hexBinary\" length=\"8\">([0-9A-F]{16})</title_id>', line)
                if title_match:
                    title_id = title_match.group(1)
                    break
        get_title_id.title_id = (title_id[0:7] + '0', title_id[8:])
    return get_title_id.title_id


def guess_update_dir(cemu_dir: Path = None, game_dir: Path = None) -> Path:
    if not cemu_dir:
        cemu_dir = get_cemu_dir()
    mlc_dir = cemu_dir / 'mlc01' / 'usr' / 'title'
    title_id = get_title_id(game_dir)
    # First try the 1.15.11c mlc layout
    if (mlc_dir / f'{title_id[0][0:7]}E' / title_id[1] / 'content').exists():
        return mlc_dir / f'{title_id[0][0:7]}E' / title_id[1] / 'content'
    # Then try the legacy layout
    elif (mlc_dir / title_id[0] / title_id[1] / 'content').exists():
        return mlc_dir / title_id[0] / title_id[1] / 'content'
    return None


def get_update_dir() -> Path:
    """ Gets the path to the game's update files in the Cemu mlc directory """
    if not hasattr(get_update_dir, 'update_dir'):
        try:
            get_update_dir.update_dir = Path(get_settings('update_dir'))
            if not get_update_dir.update_dir.exists():
                raise FileNotFoundError()
        except:
            e = FileNotFoundError('The BOTW update directory has moved or has not been saved yet.')
            e.error_text = ('The BOTW update directory has moved or has not been saved yet.')
            raise e
    return get_update_dir.update_dir


def guess_aoc_dir(cemu_dir: Path = None, game_dir: Path = None) -> Path:
    if not cemu_dir:
        cemu_dir = get_cemu_dir()
    mlc_dir = cemu_dir / 'mlc01' / 'usr' / 'title'
    title_id = get_title_id(game_dir)
    # First try the 1.15.11c mlc layout
    if (mlc_dir / f'{title_id[0][0:7]}C' / title_id[1] / 'content' / '0010').exists():
        return mlc_dir / f'{title_id[0][0:7]}C' / title_id[1] / 'content' / '0010'
    # Then try the legacy layout
    elif (mlc_dir / title_id[0] / title_id[1] / 'aoc' / 'content' / '0010').exists():
        return mlc_dir / title_id[0] / title_id[1] / 'aoc' / 'content' / '0010'
    return None


def get_aoc_dir() -> Path:
    """ Gets the path to the game's aoc files in the Cemu mlc direcroy """
    if not hasattr(get_aoc_dir, 'aoc_dir'):
        try:
            get_aoc_dir.aoc_dir = Path(get_settings('dlc_dir'))
            if not get_aoc_dir.aoc_dir.exists():
                raise FileNotFoundError()
        except:
            e = FileNotFoundError('The BOTW DLC directory has moved or has not been saved yet.')
            e.error_text = ('The BOTW DLC directory has moved or has not been saved yet.')
            raise e
    return get_aoc_dir.aoc_dir


def get_modpack_dir() -> Path:
    """ Gets the Cemu graphic pack directory for mods """
    return get_data_dir() / 'mods'


def get_util_dirs() -> tuple:
    """
    Gets the primary directories BCML uses

    :returns: A tuple containing the root BCML directory, the BCML working
    directory, the Cemu installation directory, and the Cemu graphicPacks
    directory.
    :rtype: (class:`pathlib.Path`, class:`pathlib.Path`, class:`pathlib.Path`,
            class:`pathlib.Path`)
    """
    return get_exec_dir(), get_work_dir(), get_cemu_dir(), get_modpack_dir()


def get_botw_dirs() -> tuple:
    """
    Gets the directories the BotW game files

    :returns: A tuple containing the main BotW directory, the update directoy,
    and the aoc directory.
    :rtype: (class:`pathlib.Path`, class:`pathlib.Path`, class:`pathlib.Path`)
    """
    return get_game_dir(), get_update_dir(), get_aoc_dir()


def get_bcml_version() -> str:
    """Gets the version string for the installed copy of BCML"""
    with (get_exec_dir() / 'data' / 'version.txt').open('r') as s_file:
        setup_text = s_file.read()
    ver_match = re.search(r"version='([0-9]+\.[0-9]+(\.[0-9]+)?)'", setup_text)
    return ver_match.group(1) + (' Beta' if 'Beta' in setup_text else '')


def get_game_file(path: Union[Path, str], aoc: bool = False) -> Path:
    if str(path).startswith('content/') or str(path).startswith('content\\'):
        path = Path(str(path).replace('content/', '').replace('content\\', ''))
    if isinstance(path, str):
        path = Path(path)
    game_dir = get_game_dir()
    update_dir = get_update_dir()
    try:
        aoc_dir = get_aoc_dir()
    except FileNotFoundError:
        aoc_dir = None
    if 'aoc' in path.parts or aoc:
        if aoc_dir:
            path = Path(
                path.as_posix().replace('aoc/content/0010/', '').replace('aoc/0010/content/', '')
                .replace('aoc/content/', '').replace('aoc/0010/', '')
            )
            if (aoc_dir / path).exists():
                return aoc_dir / path
            raise FileNotFoundError(f'{path} not found in DLC files.')
        else:
            raise FileNotFoundError(f'{path} is a DLC file, but the DLC directory is missing.')
    if (update_dir / path).exists():
        return update_dir / path
    if (game_dir / path).exists():
        return game_dir / path
    elif aoc_dir and (aoc_dir / path).exists():
        return aoc_dir / path
    else:
        raise FileNotFoundError(f'File {str(path)} was not found in game dump.')


def get_nested_file_bytes(file: str, unyaz: bool = True) -> bytes:
    nests = file.split('//')
    sarcs = []
    with open(nests[0], 'rb') as s_file:
        sarcs.append(sarc.read_file_and_make_sarc(s_file))
    i = 1
    while i < len(nests) - 1:
        sarc_bytes = unyaz_if_needed(
            sarcs[i - 1].get_file_data(nests[i]).tobytes())
        sarcs.append(sarc.SARC(sarc_bytes))
        i += 1
    file_bytes = sarcs[-1].get_file_data(nests[-1]).tobytes()
    if file_bytes[0:4] == b'Yaz0' and unyaz:
        file_bytes = decompress(file_bytes)
    del sarcs
    return file_bytes


def get_master_modpack_dir() -> Path:
    master = get_modpack_dir() / '9999_BCML'
    if not (master / 'rules.txt').exists():
        create_bcml_graphicpack_if_needed()
    return master


def get_hash_table() -> {}:
    if not hasattr(get_hash_table, 'table'):
        with (get_exec_dir() / 'data' / 'hashtable.json').open('r') as h_file:
            get_hash_table.table = json.load(h_file)
    return get_hash_table.table


def get_canon_name(file: str, allow_no_source: bool = False) -> str:
    if isinstance(file, str):
        file = Path(file)
    name = file.as_posix()\
        .replace("\\", "/")\
        .replace('atmosphere/titles/01007EF00011E000/romfs', 'content')\
        .replace('atmosphere/titles/01007EF00011E001/romfs', 'aoc/0010')\
        .replace('atmosphere/titles/01007EF00011E002/romfs', 'aoc/0010')\
        .replace('atmosphere/titles/01007EF00011F001/romfs', 'aoc/0010')\
        .replace('atmosphere/titles/01007EF00011F002/romfs', 'aoc/0010')\
        .replace('.s', '.')\
        .replace('Content', 'content')\
        .replace('Aoc', 'aoc')
    if 'aoc/' in name:
        return name.replace('aoc/content', 'aoc').replace('aoc', 'Aoc')
    elif 'content/' in name and '/aoc' not in name:
        return name.replace('content/', '')
    elif allow_no_source:
        return name


def get_mod_id(mod_name: str, priority: int) -> str:
    return f'{priority:04}_' + re.sub(r'(?u)[^-\w.]', '', mod_name.strip().replace(' ', ''))


def get_mod_by_priority(priority: int) -> Union[Path, bool]:
    try:
        return list(get_modpack_dir().glob(f'{priority:04}*'))[0]
    except IndexError:
        return False


def get_file_language(file: Union[Path, str]) -> str:
    if isinstance(file, Path):
        file = str(file)
    lang_match = re.search(r'_([A-Z]{2}[a-z]{2})', file)
    return lang_match.group(1)


def is_file_modded(name: str, file: Union[bytes, Path], count_new: bool = True) -> bool:
    contents = file if isinstance(file, bytes) else \
        file.read_bytes() if isinstance(file, Path) else file.tobytes()
    table = get_hash_table()
    if name not in table:
        return count_new
    fhash = xxhash.xxh32(contents).hexdigest()
    return not fhash in table[name]


def is_file_sarc(path: str) -> bool:
    ext = os.path.splitext(str(path))[1]
    return ext in SARC_EXTS


def decompress_file(file) -> bytes:
    if isinstance(file, str):
        file = Path(file)
    return decompress(file.read_bytes())


def unyaz_if_needed(file_bytes: bytes) -> bytes:
    if file_bytes[0:4] == b'Yaz0':
        return decompress(file_bytes)
    else:
        return file_bytes


def inject_file_into_bootup(file: str, data: bytes, create_bootup: bool = False):
    bootup_path = get_master_modpack_dir() / 'content' / 'Pack' / 'Bootup.pack'
    if bootup_path.exists() or create_bootup:
        if not bootup_path.exists():
            bootup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(get_game_file('Pack/Bootup.pack'), bootup_path)
        with bootup_path.open('rb') as b_file:
            old_bootup = sarc.read_file_and_make_sarc(b_file)
            new_bootup = sarc.make_writer_from_sarc(old_bootup)
        if file in old_bootup.list_files():
            new_bootup.delete_file(file)
        new_bootup.add_file(file, data)
        bootup_path.write_bytes(new_bootup.get_bytes())
    else:
        raise FileNotFoundError('Bootup.pack is not present in the master BCML mod')


def get_mod_preview(mod: BcmlMod, rules: ConfigParser = None) -> Path:
    if not rules:
        rules = RulesParser()
        rules.read(str(mod.path / 'rules.txt'))
    if 'url' in rules['Definition']:
        url = str(rules['Definition']['url'])
    if not list(mod.path.glob('thumbnail.*')):
        if 'image' not in rules['Definition']:
            if 'url' in rules['Definition'] and 'gamebanana.com' in url:
                response = urllib.request.urlopen(url)
                rdata = response.read().decode()
                img_match = re.search(
                    r'<meta property=\"og:image\" ?content=\"(.+?)\" />', rdata)
                if img_match:
                    image_path = 'thumbnail.jfif'
                    urllib.request.urlretrieve(
                        img_match.group(1),
                        str(mod.path / image_path)
                    )
                else:
                    raise IndexError(f'Rule for {url} failed to find the remote preview')
            else:
                raise KeyError(f'No preview image available')
        else:
            image_path = str(rules['Definition']['image'])
            if image_path.startswith('http'):
                urllib.request.urlretrieve(
                    image_path,
                    str(mod.path / ('thumbnail.' + image_path.split(".")[-1]))
                )
                image_path = 'thumbnail.' + image_path.split(".")[-1]
            if not os.path.isfile(str(mod.path / image_path)):
                raise FileNotFoundError(
                    f'Preview {image_path} specified in rules.txt not found')
    else:
        for thumb in mod.path.glob('thumbnail.*'):
            image_path = thumb
    return mod.path / image_path


def get_mod_link_meta(rules: ConfigParser = None):
    url = str(rules['Definition']['url'])
    mod_domain = ''
    if 'www.' in url:
        mod_domain = url.split('.')[1]
    elif 'http' in url:
        mod_domain = url.split('//')[1].split('.')[0]
    site_name = mod_domain.capitalize()
    fetch_site_meta = True
    if 'site_meta' not in get_settings():
        set_site_meta('')
    if len(get_settings('site_meta').split(';')) > 1:
        for site_meta in get_settings('site_meta').split(';'):
            if site_meta.split(':')[0] == mod_domain:
                fetch_site_meta = False
                site_name = site_meta.split(':')[1]
    if fetch_site_meta:
        try:
            response = urllib.request.urlopen(url)
            rdata = response.read().decode()
            name_match = re.search(
                r'property=\"og\:site_name\"[^\/\>]'
                r'*content\=\"(.+?)\"|content\=\"(.+?)\"[^\/\>]'
                r'*property=\"og\:site_name\"',
                rdata
            )
            if name_match:
                for group in name_match.groups():
                    if group is not None:
                        set_site_meta(f'{mod_domain}:{group}')
                        site_name = str(group)
            img_match = re.search(
                r'<link.*rel=\"(shortcut icon|icon)\".*href=\"(.+?)\".*>', rdata)
            if img_match:
                (get_exec_dir() / 'work_dir' / 'cache' / 'site_meta').mkdir(
                    parents=True,
                    exist_ok=True
                )
                try:
                    urllib.request.urlretrieve(
                        img_match.group(2),
                        str(get_exec_dir() / 'work_dir' / 'cache' / "site_meta" /\
                            f'fav_{site_name}.{img_match.group(2).split(".")[-1]}')
                    )
                except (urllib.error.URLError,
                        urllib.error.HTTPError,
                        urllib.error.ContentTooShortError):
                    pass
        except (urllib.error.URLError,
                urllib.error.HTTPError,
                urllib.error.ContentTooShortError):
            pass
    favicon = ''
    for file in (get_exec_dir() / "work_dir" / "cache" / "site_meta")\
                .glob(f'fav_{site_name}.*'):
        favicon = f'<img src="{file.resolve()}" height="16"/> '
    return f'<b>Link: <a style="text-decoration: none;" href="{url}">{favicon} {site_name}</a></b>'


def get_installed_mods(disabled: bool = False) -> List[BcmlMod]:
    return sorted({
        BcmlMod.from_info(info) for info in get_modpack_dir().glob('*/info.json') \
            if not (info.parent.stem == '9999_BCML' and (
                not disabled and (info.parent / '.disabled').exists()
            ))
    }, key=lambda mod: mod.priority)


def update_bcml():
    subprocess.call([sys.executable, '-m', 'pip', 'install', '--upgrade', 'bcml'])


def create_bcml_graphicpack_if_needed():
    """Creates the BCML master modpack if it doesn't exist"""
    bcml_mod_dir = get_modpack_dir() / '9999_BCML'
    (bcml_mod_dir / 'logs').mkdir(parents=True, exist_ok=True)
    rules = bcml_mod_dir / 'rules.txt'
    if not rules.exists():
        with rules.open('w', encoding='utf-8') as r_file:
            r_file.write('[Definition]\n'
                         'titleIds = 00050000101C9300,00050000101C9400,00050000101C9500\n'
                         'name = BCML\n'
                         'path = The Legend of Zelda: Breath of the Wild/Mods/BCML\n'
                         'description = Complete pack of mods merged using BCML\n'
                         'version = 4\n'
                         'fsPriority = 9999')


def dict_merge(dct: dict, merge_dct: dict, overwrite_lists: bool = False):
    for k in merge_dct:
        if (k in dct and isinstance(dct[k], dict)
                and isinstance(merge_dct[k], Mapping)):
            dict_merge(dct[k], merge_dct[k])
        elif (k in dct and isinstance(dct[k], list)
              and isinstance(merge_dct[k], list)):
            if overwrite_lists:
                dct[k] = merge_dct[k]
            else:
                dct[k].extend(merge_dct[k])
        else:
            dct[k] = merge_dct[k]


def create_schema_handler():
    # pylint: disable=import-error,undefined-variable
    import platform
    if platform.system() == 'Windows':
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\Classes\bcml') as key:
            try:
                winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r'Software\Classes\bcml\shell\open\command',
                    0,
                    winreg.KEY_READ
                )
            except (WindowsError, OSError):
                winreg.SetValueEx(key, 'URL Protocol', 0, winreg.REG_SZ, '')
                with winreg.CreateKey(key, r'shell\open\command') as key2:
                    if (Path(os.__file__).parent.parent / 'Scripts' / 'bcml.exe').exists():
                        exec_path = Path(os.__file__).parent.parent / 'Scripts' / 'bcml.exe'
                    elif (Path(__file__).parent.parent.parent / 'bin' / 'bcml.exe').exists():
                        exec_path = (Path(__file__).parent.parent.parent / 'bin' / 'bcml.exe')
                    else:
                        return
                    winreg.SetValueEx(key2, '', 0, winreg.REG_SZ, f'"{exec_path.resolve()}" "%1"')


class RulesParser(ConfigParser):
    def __init__(self):
        ConfigParser.__init__(self, dict_type=MultiDict)

    def write(self, fileobject):
        from io import StringIO
        buf = StringIO()
        ConfigParser.write(self, buf)
        config_str = re.sub(r'\[Preset[0-9]+\]', '[Preset]', buf.getvalue())
        fileobject.write(config_str)


class MultiDict(OrderedDict):
    _unique = 0

    def __setitem__(self, key, val):
        if isinstance(val, dict) and key == 'Preset':
            self._unique += 1
            key += str(self._unique)
        OrderedDict.__setitem__(self, key, val)


class InstallError(Exception):
    pass

class MergeError(Exception):
    pass


class Messager:
    def __init__(self, window: Window):
        self.window = window
        self.log = get_data_dir() / 'bcml.log'

    def write(self, string: str):
        from .__main__ import LOG
        if string.strip('') not in {'', '\n'} and not string.startswith('VERBOSE'):
            self.window.evaluate_js(f'window.onMsg(\'{string}\');')
        with LOG.open('a', encoding='utf-8') as log_file:
            if string.startswith('VERBOSE'):
                string = string[7:]
            log_file.write(f'{string}\n')