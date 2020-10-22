#!/usr/bin/env python3.9
import os
import platform
import subprocess
import beets
import optparse
import glob
import urllib
import json
import pathlib
import fnmatch
import re
from copy import copy
from optparse import OptionParser, Option, OptionValueError
from beets import ui
from beets.plugins import BeetsPlugin

PLUGIN_STAGE = u'r'
PLUGIN_VERSION = u'1.0.0'

#
# OPTION PARSER TYPE CLASS
#
def check_list ( option, opt, value ):
    try:
        return value.split( ',' )
    except ValueError:
        raise OptionValueError from ValueError ( u'Option {}: Invalid list value: {}'.format( opt, value ) )

class OptParseOption ( optparse.Option ):
    TYPES = optparse.Option.TYPES + ( 'list', )
    TYPE_CHECKER = copy( optparse.Option.TYPE_CHECKER )
    TYPE_CHECKER['list'] = check_list

#
# PLAYLISTCONVERTER PLUGIN DEFINITION
#
class PlayConvPlug ( beets.plugins.BeetsPlugin ):

    # Initialize plugin
    def __init__ ( self ):
        super( PlayConvPlug, self ).__init__()

        # Set defaults (dependent on current os)
        self._possible_formats = [ u'posix', u'ntfs', u'uriposix', u'urintfs' ]
        self._default_source_dir = { 'Linux': u'posix', 'Windows': u'ntfs' }.get( platform.system(), u'posix' )
        self._default_playlist_path = pathlib.Path( beets.config['playlist']['playlist_dir'].as_filename() ).resolve()
        if self._default_source_dir == u'posix':
            self._default_playlist_posix = self._default_playlist_path
        else:
            self._default_playlist_posix = pathlib.Path( self._default_playlist_path.with_stem( self._default_playlist_path.stem + u'POSIX' ) )
        if self._default_source_dir == u'ntfs':
            self._default_playlist_ntfs = self._default_playlist_path
        else:
            self._default_playlist_ntfs = pathlib.Path( self._default_playlist_path.with_stem( self._default_playlist_path.stem + u'NTFS' ) )
        self._default_playlist_uriposix = pathlib.Path( self._default_playlist_path.with_stem( self._default_playlist_path.stem + u'URIPOSIX' ) )
        self._default_playlist_urintfs = pathlib.Path( self._default_playlist_path.with_stem( self._default_playlist_path.stem + u'URINTFS' ) )
        self._default_types = self._possible_formats.copy()
        self._default_types.remove( self._default_source_dir )

        # Add configuration options and set defaults
        self.config.add({
            'auto': False,
            'types': ' '.join( self._default_types ),
            'source_dir': self._default_source_dir,
            'playlist_posix': str( self._default_playlist_posix ),
            'playlist_ntfs': str( self._default_playlist_ntfs ),
            'playlist_uriposix': str( self._default_playlist_uriposix ),
            'playlist_urintfs': str( self._default_playlist_urintfs )
        })

        # Create commandline parser
        self._parser = optparse.OptionParser( option_class=OptParseOption, version=PLUGIN_VERSION, description=u'Covert playlists between different formats. You can either import a new playlist from a given format or export your playlists to specified formats.', add_help_option=True, prog=u'PlaylistConverter', epilog=u'For more information see https://github.com/moritzgrede/beets-PlaylistConverter' )
        self._parser.add_option( u'-f', u'--file', dest='filename', action='store', type='list', help=u'The filename to export from OR import to. Multiple values accepted, seperate with ","' )
        self._parser.add_option( u'-p', u'--path', dest='filepath', action='store', type='list', help=u'The filepath to export to OR import from. Multiple values accepted, seperate with ","' )
        self._parser.add_option( u'-c', u'--show-changes', dest='show_changes', default=False, action='store_true', help=u'Show the difference between the original file and the converted one' )
        self._parser.add_option( u'-q', u'--quiet', dest='quiet', action='store_true', help=u'Run in quiet mode (no output, except critical errors)' )
        
        # 'import' group of parser
        self._parser_import = optparse.OptionGroup( self._parser, u'Import', u'Use this to import one or more playlists to your source playlist directory' )
        self._parser_import.add_option( u'-i', u'--import', dest='do_import', action='store_true', help=u'Import playlists to source directory', default=False )
        self._parser_import.add_option( u'-a', u'--append', dest='append', action='store_true', default=False, help=u'Append new items to existing playlist' )

        # 'export' group of parser
        self._parser_export = optparse.OptionGroup( self._parser, u'Export', u'Use this to export one or more playlists to defined formats' )
        self._parser_export.add_option( u'-e', u'--export', dest='do_export', action='store_true', help=u'Export playlists to specified formats', default=False )
        self._parser_export.add_option( u'-t', u'--types', dest='types', action='store', type='list', help=u'Define types to export to. Multiple values accepted, seperate with ","' )

        # Add groups to parser
        self._parser.add_option_group( self._parser_import )
        self._parser.add_option_group( self._parser_export )

        # Add subcommand to beets
        self._command = ui.Subcommand( u'playconv', self._parser, u'Convert playlists between different formats', [ u'plcv' ] )

        # Register an import listener
        if ( self.config['auto'].get( bool ) ):
            self.register_listener( 'import', self._exportPlaylists )
            self._log.debug( u'Import listener registered' )

    # Define command to be executed from subcommand
    def commands ( self ):

        self._command.func = self._playconv
        return [ self._command ]

    # Function to execute from subcommand
    def _playconv ( self, lib, opts, args ):

        self._log.debug( '{}', str( opts ) )

        # Resolve plugin config
        self.config.resolve()
        self._log.debug( '{}', str( self.config ) )

        # Check for quiet operation
        if opts.quiet:
            builtins.print = lambda args: None

        # Throw error, if multiple commands have been set
        if opts.do_import and opts.do_export:

            raise beets.ui.UserError( u'Cannot execute multiple commands at the same time. Only define one command to perform' )

        # If import has been chosen
        elif opts.do_import:

            self._log.debug( 'Do import' )

            # Check if a filepath has been defined
            if opts.filepath is not None:

                # If filenames have been defined
                if opts.filename is not None:
                    # Check if as many filepaths as filenames have been defined
                    if opts.filepath.count() != opts.filename.count():
                        # If not throw unrecoverable error
                        raise beets.ui.UserError( u'Not as many filenames as filepaths have been defined' )

                # Do import
                self.do_import( opts )

            # Else throw an unrecoverable error
            else:
                raise beets.ui.UserError( u'No filepath defined for import' )

        # If export has been chosen
        else:

            self._log.debug( 'Do export' )

            # Do export
            self.do_export( opts )

    # Function to import a playlist
    def do_import ( self, opts ):

        # Loop through given filepaths
        for index, filepath in enumerate( opts.filepath ):

            self._log.debug( 'Importing: {0}', filepath )

            try:
                # Resolve the given filepath
                playlist_import = pathlib.Path( filepath.strip( ' ,' ) ).resolve( True )
                self._log.debug( 'Path resolved to: {0}', playlist_import )

                # Checking if given path is directory
                if playlist_import.is_dir():
                    playlist_import = playlist_import.glob( '*' )
                else:
                    playlist_import = [ playlist_import ]

                for p in playlist_import:

                    print( beets.ui.colorize( 'text_highlight_minor', 'Importing file {0}'.format( p ) ) )

                    # Create new filepath
                    if opts.filename is None:
                        new_filename = p.name
                    elif opts.filename[index].endswith( '*.m3u' ):
                        new_filename = opts.filename[index]
                    else:
                        new_filename = opts.filename[index] + '.m3u'

                    new_filepath = {
                        self.config['source_dir'].as_str(): pathlib.PurePath( self.config[ 'playlist_' + self.config['source_dir'].as_str() ].as_filename(), new_filename )
                    }

                    # Convert file
                    self.convert_playlist( p, new_filepath, [ self.config['source_dir'].as_str() ], known_source=False, show_diff=opts.show_changes, append=opts.append )

            except FileNotFoundError:
                print( beets.ui.colorize( 'text_error', u'The filepath could not be found for: {}'.format( filepath ) ) )

    # Function to export a playlist
    def do_export ( self, opts ):

            # Check if no filename has been defined
            if opts.filename is None:
                opts.filename = [ self.config[ 'playlist_' + self.config['source_dir'].as_str() ].as_filename() ]
            self._log.debug( u'The following filenames have been passed: {0}', opts.filename )

            # Check if no types have been defined
            if opts.types is None:
                opts.types = self.config['types'].as_str_seq( True )
            self._log.debug( u'The following types have been passed: {0}', opts.types )

            # Check if no path has been defined
            new_filepath = dict()
            if opts.filepath is None:
                for t in opts.types:
                    new_filepath[t] = self.config[ 'playlist_' + t ].as_str()
            else:
                for index, t in enumerate( opts.types ):
                    new_filepath[t] = opts.filepath[index]
            opts.filepath = new_filepath
            self._log.debug( u'The following filepaths have been passed: {0}', opts.filepath )

            # Printing the selected types and there export paths
            print( u'Exporting playlists:' )
            for k, v in opts.filepath.items():
                print( u'"{0}" to "{1}"'.format( k, v ) )

            # Loop through given filenames
            for filename in opts.filename:

                self._log.debug( 'Exporting: {0}', filename )

                try:
                    # Resolve the given filename
                    playlist_export = pathlib.Path( self.config[ 'playlist_' + self.config['source_dir'].as_str() ].as_filename(), filename.strip( ' ,' ) ).resolve( True )
                    self._log.debug( 'Path resolved to: {0}', playlist_export )

                    # Checking if given path is directory
                    if playlist_export.is_dir():
                        playlist_export = playlist_export.glob( '*' )
                    else:
                        playlist_export = [ playlist_export ]

                    # For each given playlist to export
                    for p in playlist_export:

                        print( beets.ui.colorize( 'text_highlight_minor', 'Exporting file {0}'.format( p ) ) )

                        # Convert file
                        self.convert_playlist( p, opts.filepath, opts.types, known_source=True, show_diff=opts.show_changes, append=opts.append )

                except FileNotFoundError:
                    print( beets.ui.colorize( 'text_error', u'The filepath could not be found for file: {}'.format( filename ) ) )

    # Function to check for updates
    def do_updatecheck ( self ):

        # Stage association dictionary
        stage_assc = {
            'a': 'Alpha',
            'b': 'Beta',
            'rc': 'Release Candidate',
            'r': 'Release'
        }
        
        # Print current version
        print( 'Currently running {0} {1}'.format( stage_assc[PLUGIN_STAGE], PLUGIN_VERSION ) )

        try:
            # Query GitHub
            web_request = urllib.request.urlopen( 'https://api.github.com/repos/moritzgrede/beets-PlaylistConverter/releases/latest', timeout=5 )

            # Parse json content
            json_data = json.loads( web_request.read().decode( web_request.info().get_content_charset( 'utf-8' ) ) )

            # Parse version tag
            stage = re.search( '^+\D', json_data['tag_name'] ).group( 1 )
            version = re.search( '$+\d', json_data['tag_name'] ).group( 1 )

            # Print newest version
            print( 'Newest available is {0} {1}'.format( stage_assc[stage], version ) )

        except Exception:
            raise( beets.ui.UserError( u'Whil checking for updates an error occurred' ) )

    # Function to convert a playlist
    def convert_playlist ( self, playlist_read, playlist_write_assc, dest_formats, known_source, show_diff, append ):

        # List of new playlist contents
        converted_playlist_content = {
            'posix': [],
            'ntfs': [],
            'uriposix': [],
            'urintfs': []
        }
        playlist_content_diff = {
            'posix': [],
            'ntfs': [],
            'uriposix': [],
            'urintfs': []
        }
        self._log.debug( u'convert_playlist passed formats: {0}', dest_formats )
        playlist_read = pathlib.PurePath( playlist_read )

        try:
            # Open file for reading
            self._log.debug( 'Opening file for reading' )
            with open( playlist_read, 'rt', encoding='utf-8' ) as file:

                # Iterate through each line
                for line in file:

                    line = line.strip( '\r\n ' )
                    self._log.debug( 'File "{1}": Processing line: {0}', line, playlist_read.name )

                    # Convert line into each destination format
                    for dest_format in dest_formats:

                        self._log.debug( 'Converting to: {0}', dest_format )

                        # Check if the line is a comment / extended m3u tag
                        if line.startswith( '#' ):
                            self._log.debug( 'Comment found' )
                            converted_playlist_content[dest_format].append( line )

                        # Else try to create the filepath and add it
                        else:

                            # If the source is known, convert without checking for file existence (aka while exporting)
                            if known_source:
                                converted_line = self.convert_path( line, dest_format )
                            
                            # Otherwise check the created path for its existence (aka while importing)
                            else:
                                converted_line = self.convert_pure_path( line, dest_format, True )

                            self._log.debug( 'Parsed line: {0}', converted_line )

                            # Only add to content if not None
                            if converted_line is not None:
                                converted_playlist_content[dest_format].append( str( converted_line ) )
                                playlist_content_diff[dest_format].append( ( line, str( converted_line ) ) )

            # Again loop through all destination formats to save the created files
            for dest_format in dest_formats:

                # Check if there is any content to save (filtering out comments / extended m3u tags)
                if len( fnmatch.filter( converted_playlist_content[dest_format], '#*' ) ) != len( converted_playlist_content[dest_format] ):

                    if show_diff:
                        # Show differences between files
                        beets.ui.show_path_changes( playlist_content_diff[dest_format] )

                    # Get current destination
                    playlist_write = pathlib.Path( playlist_write_assc[dest_format] )

                    # Check if a directory has been given to save files to
                    if playlist_write.suffix == '':
                        # Append original filename and current type to path
                        playlist_write = pathlib.Path( playlist_write, playlist_read.stem + playlist_read.suffix )
                    self._log.debug( u'Create a new playlist at: {0}', str( playlist_write ) )
                    print( beets.ui.colorize( 'text_highlight_minor', u'Saving new playlist to: {0}'.format( str( playlist_write ) ) ) )

                    # Check if file exists
                    if playlist_write.exists() and append:
                        # Get current content
                        current_content = playlist_write.read_text( encoding='utf-8' )

                        # Add new content to current content
                        converted_playlist_content[dest_format] = [current_content] + converted_playlist_content[dest_format]

                    # Create all folders and write to file
                    try:
                        playlist_write.parent.mkdir( parents=True, exist_ok=True )
                        playlist_write.write_text( '\n'.join( converted_playlist_content[dest_format] ), encoding='utf-8' )
                    except OSError:
                        print( beets.ui.colorize( 'text_error', u'Error while saving the playlist to: {0}'.format( str( playlist_write ) ) ) )

                else:
                    print( beets.ui.colorize( 'text_warning', u'Playlist could not be converted, no content to save' ) )

        except OSError:
            print( beets.ui.colorize( 'text_error', u'Error while reading the file: {}'.format( str( playlist_read ) ) ) )

    # Function to convert a raw unknown path to specific format
    def convert_pure_path ( self, pure_path, dest_format, check_existence ):

        # This function is dirty...Don't look at it. Actually do and make changes if you've got an better idea

        # Check if uriposix exists
        def check_uriposix ( uriposix ):
            try:
                pathlib.PosixPath( self.str_to_uriposix( uriposix ) ).resolve( True ) | os.devnull
                return True
            except FileNotFoundError:
                return False

        # Check if urintfs exists
        def check_urintfs ( urintfs ):
            try:
                pathlib.WindowsPath( self.str_to_urintfs( urintfs ) ).resolve( True ) | os.devnull
                return True
            except FileNotFoundError:
                return False

        # Create pure paths for all different types
        pure_posix_path = pathlib.PurePosixPath( pure_path )
        self._log.debug( 'PurePosixPath: {0}', pure_posix_path )
        pure_ntfs_path = pathlib.PureWindowsPath( pure_path )
        self._log.debug( 'PureNTFSPath: {0}', pure_ntfs_path )
        pure_uriposix_path = pathlib.PurePosixPath( self.str_to_uriposix( pure_path ) )
        self._log.debug( 'PureURIPosixPath: {0}', pure_uriposix_path )
        pure_urintfs_path = pathlib.PureWindowsPath( self.str_to_urintfs( pure_path ) )
        self._log.debug( 'PureURINTFSPath: {0}', pure_urintfs_path )

        # Depending on the destination format try to convert the path
        if dest_format == 'posix':
            # posix format conversion
                            
            # posix to posix
            converted_path = self.posix_to_posix( pure_posix_path, check_existence )
            self._log.debug( 'Posix to Posix. Type: {0}, Line: {1}', type( converted_path ), converted_path )
            if type( converted_path ) is pathlib.PosixPath:
                return converted_path

            # ntfs to posix
            converted_path = self.ntfs_to_posix( pure_ntfs_path, check_existence )
            self._log.debug( 'NTFS to Posix. Type: {0}, Line: {1}', type( converted_path ), converted_path )
            if type( converted_path ) is pathlib.PosixPath:
                return converted_path

            # uriposix to posix
            converted_path = self.posix_to_posix( pure_uriposix_path, check_existence )
            self._log.debug( 'URIPosix to Posix. Type: {0}, Line: {1}', type( converted_path ), converted_path )
            if type( converted_path ) is pathlib.PosixPath:
                return converted_path

            # urintfs to posix
            converted_path = self.ntfs_to_posix( pure_urintfs_path, check_existence )
            self._log.debug( 'URINTFS to Posix. Type: {0}, Line: {1}', type( converted_path ), converted_path )
            if type( converted_path ) is pathlib.PosixPath:
                return converted_path

        elif dest_format == 'ntfs':
            # ntfs format conversion

            # posix to ntfs
            converted_path = self.posix_to_ntfs( pure_posix_path, check_existence )
            self._log.debug( 'Posix to NTFS. Type: {0}, Line: {1}', type( converted_path ), converted_path )
            if type( converted_path ) is pathlib.WindowsPath:
                return converted_path

            # ntfs to ntfs
            converted_path = self.ntfs_to_ntfs( pure_ntfs_path, check_existence )
            self._log.debug( 'NTFS to NTFS. Type: {0}, Line: {1}', type( converted_path ), converted_path )
            if type( converted_path ) is pathlib.WindowsPath:
                return converted_path

            # uriposix to ntfs
            converted_path = self.posix_to_ntfs( pure_uriposix_path, check_existence )
            self._log.debug( 'URIPosix to NTFS. Type: {0}, Line: {1}', type( converted_path ), converted_path )
            if type( converted_path ) is pathlib.WindowsPath:
                return converted_path

            # urintfs to ntfs
            converted_path = self.ntfs_to_ntfs( pure_urintfs_path, check_existence )
            self._log.debug( 'URINTFS to NTFS. Type: {0}, Line: {1}', type( converted_path ), converted_path )
            if type( converted_path ) is pathlib.WindowsPath:
                return converted_path

        elif dest_format == 'uriposix':
            # uriposix format conversion

            # posix to uriposix
            converted_path = self.posix_to_uriposix( pure_posix_path, check_existence )
            self._log.debug( 'Posix to URIPosix. Type: {0}, Line: {1}', type( converted_path ), converted_path )
            if check_uriposix( converted_path ):
                return converted_path

            # ntfs to uriposix
            converted_path = self.ntfs_to_uriposix( pure_ntfs_path, check_existence )
            self._log.debug( 'NTFS to URIPosix. Type: {0}, Line: {1}', type( converted_path ), converted_path )
            if check_uriposix( converted_path ):
                return converted_path

            # uriposix to uriposix
            converted_path = self.posix_to_uriposix( pure_uriposix_path, check_existence )
            self._log.debug( 'URIPosix to URIPosix. Type: {0}, Line: {1}', type( converted_path ), converted_path )
            if check_uriposix( converted_path ):
                return converted_path

            # urintfs to uriposix
            converted_path = self.ntfs_to_uriposix( pure_urintfs_path, check_existence )
            self._log.debug( 'URINTFS to URIPosix. Type: {0}, Line: {1}', type( converted_path ), converted_path )
            if check_uriposix( converted_path ):
                return converted_path

        elif dest_format == 'urintfs':
            # uriposix format conversion

            # posix to urintfs
            converted_path = self.posix_to_urintfs( pure_posix_path, check_existence )
            self._log.debug( 'Posix to URINTFS. Type: {0}, Line: {1}', type( converted_path ), converted_path )
            if check_urintfs( converted_path ):
                return converted_path

            # ntfs to urintfs
            converted_path = self.ntfs_to_urintfs( pure_ntfs_path, check_existence )
            self._log.debug( 'NTFS to URINTFS. Type: {0}, Line: {1}', type( converted_path ), converted_path )
            if check_urintfs( converted_path ):
                return converted_path

            # uriposix to urintfs
            converted_path = self.posix_to_urintfs( pure_uriposix_path, check_existence )
            self._log.debug( 'URIPosix to URINTFS. Type: {0}, Line: {1}', type( converted_path ), converted_path )
            if check_urintfs( converted_path ):
                return converted_path

            # urintfs to urintfs
            converted_path = self.ntfs_to_urintfs( pure_urintfs_path, check_existence )
            self._log.debug( 'URINTFS to URINTFS. Type: {0}, Line: {1}', type( converted_path ), converted_path )
            if check_urintfs( converted_path ):
                return converted_path

        # If nothing has been returned yet, print return None
        return None

    def convert_path ( self, path, dest_format ):

        # Get the source directory format
        src_format = self.config['source_dir'].as_str()

        # Create function name
        func_str = src_format + u'_to_' + dest_format
        func_obj = getattr( self, func_str )
        self._log.debug( u'Calling function: {0}', func_obj )
        return func_obj(path, False)

    # Function to get mounted drives, returns list of dictionaries
    def get_mounted_drives( self ):

        # Get mounted drives
        df_process = subprocess.run( ['df', '--type=drvfs', '--portability'], capture_output=True )
        if df_process.returncode != 0:
            return None
        mounted_drives_raw = df_process.stdout.decode( 'utf-8', 'ignore' ).splitlines( False )

        # List for dictionaries of found mounted drives
        mounted_drives = []

        # Iterate through mountpoints
        for mounted_drive_raw in mounted_drives_raw[1:len( mounted_drives_raw )]:

            # Split string at ' ' and remove resulting empty items in list
            mounted_drive_raw = list( filter( None, mounted_drive_raw.split( ' ' ) ) )

            # Create directory entry
            mounted_drive = {
                'source': mounted_drive_raw[0],
                'total': mounted_drive_raw[1],
                'used': mounted_drive_raw[2],
                'available': mounted_drive_raw[3],
                'capacity': mounted_drive_raw[4],
                'mountpoint': mounted_drive_raw[5]
            }

            # Add dictionary to list
            mounted_drives.append( mounted_drive )

        # Return list of dictionaries
        return mounted_drives

    #
    # FORMAT CONVERSION FUNCTIONS
    #

    # Convert pure posix path to posix
    def posix_to_posix ( self, pure_path, must_exist ):
        try:
            path = pathlib.PurePosixPath( pure_path )
            if must_exist:
                path = pathlib.PosixPath( path ).resolve( True )
            return path
        except FileNotFoundError:
            return None
    
    # Convert pure posix path to ntfs
    def posix_to_ntfs ( self, pure_path, must_exist ):
        pure_path = str( pure_path )
        # Loop through all mounted drives
        for mounted_drive in self.get_mounted_drives():
            # Check if the pure_path starts with the mountpoint of the drive
            if pure_path.startswith( mounted_drive['mountpoint'] ):
                # Remove the mountpoint from the path
                path = pure_path[len( mounted_drive['mountpoint'] ):len( pure_path )].replace( '/', '\\' )
                try:
                    path = pathlib.PureWindowsPath( mounted_drive['source'], path )
                    if must_exist:
                        path = pathlib.WindowsPath( path ).resolve( True )
                    return path
                except FileNotFoundError:
                    return None

    # Convert pure posix path to uri posix
    def posix_to_uriposix ( self, pure_path, must_exist ):
        try:
            return self.posix_to_posix( pure_path, must_exist ).as_uri()
        except ValueError:
            return None
    
    # Convert pure posix path to urintfs
    def posix_to_urintfs ( self, pure_path, must_exist ):
        try:
            return self.posix_to_ntfs( pure_path, must_exist ).as_uri()
        except ValueError:
            return None

    # Convert pure ntfs path toposix
    def ntfs_to_posix ( self, pure_path, must_exist ):
        pure_path = str( pure_path )
        # Loop through all mounted drives
        for mounted_drive in self.get_mounted_drives():
            # Check if pure_path starts with the source of the drive
            if pure_path.startswith( mounted_drive['source'] ):
                # Remove the source from the path
                path = pure_path[len( mounted_drive['source'] ):len( pure_path )].replace( '\\', '/' )
                try:
                    path = pathlib.PurePosixPath( mounted_drive['mountpoint'], path )
                    if must_exist:
                        path = pathlib.PosixPath( path ).resolve( True )
                    return path
                except FileNotFoundError:
                    return None
    
    # Convert pure ntfs path to ntfs
    def ntfs_to_ntfs ( self, pure_path, must_exist ):
        try:
            path = pathlib.PureWindowsPath( pure_path )
            if must_exist:
                path = pathlib.WindowsPath( path ).resolve( True )
            return path
        except FileNotFoundError:
            return None
    
    # Convert pure ntfs path to uriposix
    def ntfs_to_uriposix ( self, pure_path, must_exist ):
        try:
            return self.ntfs_to_posix( pure_path, must_exist ).as_uri()
        except ValueError:
            return None
    
    # Convert pure ntfs path to urintfs
    def ntfs_to_urintfs ( self, pure_path, must_exist ):
        try:
            return self.ntfs_to_ntfs( pure_path, must_exist ).resolve( True )
        except ValueError:
            return None

    # Convert string path to uriposix
    def str_to_uriposix ( self, string ):
        try:
            return urllib.parse.unquote_plus( urllib.parse.urlparse( string ).path )
        except ValueError:
            return None

    # Convert string path to urintfs
    def str_to_urintfs ( self, string ):
        try:
            uriposix = self.str_to_uriposix( string )
            return uriposix[1:len( uriposix )]
        except ValueError:
            return None
