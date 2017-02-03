#!/usr/bin/env python3

'''
Script to start programs on different virtual desktops.

When called without a parameter start all active programs for all
active desktops.
When called with one parameter it is the name of the desktop for which
the active programs should be started.

Default the script uses the SQLite3 database:
    ~/Databases/general.sqlite
but this can be overridden with the environment variable:
    PYTHON_START_PROGRAMS_DB

The table is used for the values for:
    switch_desktop          (command used to switch to another desktop)
    default_seconds_to_wait (optional, default 10)

Active desktops are retrieved from the table desktops.
Active programs are retreived from the table desktopCommands.

Table definitions:
CREATE  TABLE desktopCommands(
    name        TEXT    NOT NULL,
    isActive    TEXT    NOT NULL DEFAULT 'T',
    command     TEXT    NOT NULL,
    indexNo     INTEGER NOT NULL,
    logDir      TEXT,
    workDir     TEXT,

    CONSTRAINT isActive  CHECK(isActive IN ('T', 'F')),

    FOREIGN KEY(name) REFERENCES desktops(name),

    PRIMARY KEY(name, command)
);
CREATE  TABLE desktops(
    name        TEXT    NOT NULL,
    isActive    TEXT    NOT NULL DEFAULT 'T',
    indexNo     INTEGER NOT NULL UNIQUE,
    value       TEXT    NOT NULL UNIQUE,
    waitSeconds INTEGER NOT NULL,

    CONSTRAINT isActive  CHECK(isActive IN ('T', 'F')),

    PRIMARY KEY(name)
);
CREATE TABLE variables (
	name    TEXT NOT NULL,
	value	TEXT NOT NULL,

	PRIMARY KEY(name)
);

'''

from os         import chdir, environ
from os.path    import dirname, expanduser, realpath
from sqlite3    import connect
from subprocess import check_call, Popen, STDOUT
from sys        import exit, argv
from time       import sleep, strftime

'''
When defined closes cursor and conn. Does a commit.
In this case a commit is not necessary, but I do it anyway:
saveguard for when the code changes.
'''
def deinit():
    global conn
    global cursor

    if cursor:
        cursor.close()
        cursor = None
    if conn:
        conn.commit()
        conn.close()
        conn   = None

def do_desktop(desktop_values):
    desktop_name    = desktop_values[0]
    desktop_value   = desktop_values[1]
    desktop_wait    = desktop_values[2]
    commands        = cursor.execute(select_commands, [desktop_name]).fetchall()
    desktop_command = (switch_desktop + desktop_value).split()
    if desktop_wait == 0:
        desktop_wait = default_seconds_to_wait
    check_call(desktop_command)
    for command_arr in commands:
        command         = command_arr[0].split()
        log_file_name   = command_arr[1]
        directory       = command_arr[2]
        if not log_file_name:
            log_file_name = '/dev/null'
        log_file_name = log_file_name.replace('%T', strftime('%F_%R'))
        with open(log_file_name, 'w') as log_file:
            Popen(command, stdout = log_file, cwd = directory, stderr = STDOUT)
    sleep(desktop_wait)

'''
Give error message.
Do a rollback when not overriden.
deinit
exit
'''
def give_error(message, do_rollback = True):
    print(message)
    if do_rollback and conn:
        conn.rollback()
    deinit()
    exit(1)

'''
Initialize global variables.
Create connection and cursor.
Uses the enironment variable PYTHON_START_PROGRAMS_DB to get the used db.
'''
def init():
    global conn
    global cursor
    global default_seconds_to_wait
    global select_commands
    global select_desktops
    global switch_desktop
    global this_desktop

    database                = environ.get('PYTHON_START_PROGRAMS_DB',
                                          '~/Databases/general.sqlite')
    default_seconds_to_wait = 10
    pragma_commands         = '''
        PRAGMA foreign_keys = ON;
    '''
    select_commands         = '''
        SELECT   command
        ,        logDir
        ,        workDir
        FROM     desktopCommands
        WHERE    name = ?
             AND isActive = 'T'
        ORDER BY indexNo
    '''
    select_desktop_template = '''
        SELECT   name
        ,        value
        ,        waitSeconds
        FROM     desktops
        WHERE    isActive = 'T'
    '''
    select_desktops         = select_desktop_template + '''
        ORDER BY indexNo
    '''
    select_one_desktop      = select_desktop_template + '''
             AND name = ?
    '''
    select_variable         = '''
        SELECT  value
        FROM    variables
        WHERE   name = ?
    '''
    this_desktop            = None

    conn    = connect(expanduser(database))
    cursor  = conn.cursor()
    cursor.execute(pragma_commands)
    if cursor.execute('PRAGMA integrity_check').fetchall()[0][0] != 'ok':
        give_error('ERROR: integrity error')
    if len(cursor.execute('PRAGMA foreign_key_check').fetchall()) != 0:
            give_error('ERROR: foreign key error')
    if len(argv) > 2:
        give_error('ERROR: %s [DESKTOP_NAME]' % argv[0])
    if len(argv) == 2:
        desktop_name = argv[1]
        result       = cursor.execute(select_one_desktop, [desktop_name]).fetchall()
        if len(result) != 1:
            give_error('ERROR: Could not find the desktop ‘%s’' % desktop_name)
        this_desktop = result[0]
    result = cursor.execute(select_variable, ['switchDesktop']).fetchall()
    if len(result) != 1:
        give_error('ERROR: Could not find desktop switch command')
    switch_desktop = result[0][0]
    result = cursor.execute(select_variable, ['waitBeforeSwitchDesktop']).fetchall()
    if len(result) > 1:
        give_error('ERROR: something went wrong with retreiving wait seconds')
    if len(result) == 1:
        default_seconds_to_wait = int(result[0][0])
    chdir(expanduser('~'))

init()

if this_desktop:
    do_desktop(this_desktop)
else:
    for desktop in cursor.execute(select_desktops).fetchall():
        do_desktop(desktop)

deinit()
