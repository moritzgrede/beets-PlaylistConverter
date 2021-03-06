# beets-PlaylistConverter

You often switch between filesystems? Your favourite music player does not support a specific path type in .m3u files?

With this [beets][beets-docs] plugin you can convert playlists to three other formats. It supports the posix-style path format of `/foo/bar`, the ntfs-style of `C:\foo\bar` and their uri counterparts, so `file:///foo/bar` and `file:///C:/foo/bar`.

## Getting Started

You will need Python <= 3.9.0 and the bleeding edge version of beets.

```shell
$ python3.9 -m pip install --upgrade https://github.com/repos/beetbox/beets/tarball/master beets-playlistconverter
```

Then, [enable the plugin][beets-using plugins]. You may use the `beet config --edit`
command to add the *playlistconverter* plugin to the configuration.

```yaml
plugins: … playlistconverter
```

Now, you can further configure the plugin or start using it.

## Configuration

The following sample configuration snippet shows the available options. Where to place this snippet in the [config.yaml][beets-config] is shown [here][beets-using plugins]

```yaml
playlistconverter:
  auto: no
  source_dir: posix
  types: ntfs uriposix urintfs
  playlist_posix: /foo/bar
  playlist_ntfs: /foo/barNTFS
  playlist_uriposix: /foo/barURIPOSIX
  playlist_urintfs: /foo/barURINTFS
```

- `auto`

  Can be either `yes` or `no` (`True` or `False`). It configures the automated call of the plugin after an import of any kind. This way, if any of the playlists in the source directory have changed due to database changes, the playlists will be converted again.

- `source_dir`

  Configures the source directory type of your playlists. This does not define the actual path, only the type. Can be either `posix` or `ntfs` depending on your OS. Default is to get the current OS and set the type accordingly (it would be wise to set this by hand).

- `types`

  Will define a default set of type to convert to. This is a space seperated list of the following values: `posix ntfs uriposix urintfs`. The order does actually matter, the type named first will be also be converted first (Although this doesn't really make a siginificant difference). By default all available types except for the one defined in `source_dir` are included.

- `playlist_*`

  Next the different options for playlist paths. These start with `playlist_` and end in one of the possible formats. All of these are paths. By default the `playlist_` path with the `source_dir` type is the path defined in the [`playlist`][beets-playlist] plugin configuration. Then all other types will get the same path with their respective type appended.

It is recommended to also enable the [playlist][beets-playlist] plugin and configure both to the same directory. This way the playlist plugin will keep your source playlists up to date and the playlistconverter will convert the files.

## Usage

```shell
$ beet plcv -h
```

Shows help for all available commands `-h` / `--help`.

```shell
$ beet plcv -c -s [OPTIONS]
```

Show changes made between different format conversions `-c` / `--show-changes`. To show no output except for errors use `-q` / `--quiet`.

### Importing

```shell
$ beet plcv -i -f FILENAME -p FILEPATH -a
```

Import a file or directory `-p` / `--path` to one or multiple files in the source directory `-f` / `--file`. If importing to an existing source file (or importing a folder), specify `-a` / `--append` to append to the existing file instead of overwriting.<br />
Multiple values for `FILEPATH` and `FILENAME` are also possible, use `,` as a seperator.

### Exporting

```shell
$ beet plcv -e
```

Defining no other options will read the [Configuration](#Configuration) and export all formats (except the sources format) to the specified directorys, overwriting existing files.


```shell
$ beet plcv -e -f FILENAME -p FILEPATH -t TYPES
```

Export a source file `-f` / `--filename` to one or multiple folders or files `-p` / `--path`. Specify formats to export with `-t` / `--types` (see [Configuration - Types](#Configuration) for possible values).<br />
Multiple values for `FILENAME` and `FILEPATH` are also possible, use `,` as a seperator. When multiple `FILEPATH`s are defined, then each will be associated with a type.

## Feature Requests / Bug reports

If you have an idea or a use case this plugin is missing or even found a bug, feel free to
[open an issue](https://github.com/moritzgrede/beets-PlaylistConverter/issues/new).

### Planned additions
The following is a list of possible additions to the plugin.

- Checking for write times in the source directory. Ignore files that haven't changed and add commandline switch to force reading / writing
- Support relative paths in .m3u files
- Add [extended m3u](https://en.wikipedia.org/wiki/M3U#Extended_M3U) support
- m3u8 support / saving instead of m3u?


## License

The MIT License

Copyright (c) 2020 Moritz Grede

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.


[beets-docs]: https://beets.readthedocs.io/en/latest/index.html
[beets-config]: http://beets.readthedocs.io/en/latest/reference/config.html
[beets-using plugins]: http://beets.readthedocs.io/en/latest/plugins/index.html#using-plugins
[beets-playlist]: https://beets.readthedocs.io/en/latest/plugins/playlist.html