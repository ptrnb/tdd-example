from fabric.contrib.files import append, exists, sed, exists
from fabric.api import env, local, run, sudo
import random

REPO_URL = 'https://github.com/ptrnb/tdd-example.git'

def deploy():
    site_folder = '/home/{0}/sites/{1}'.format(env.user, env.host)
    source_folder = site_folder + '/source'
    _create_directory_structure_if_necessary(site_folder)
    _get_latest_source(source_folder)
    _update_settings(source_folder, env.host)
    _update_virtualenv(source_folder)
    _update_static_files(source_folder)
    _update_database(source_folder)
    _install_init_script(source_folder)

def _get_site_prefix():
    return env.host.split('.')[0]

def _create_directory_structure_if_necessary(site_folder):
    for subfolder in ('database', 'static', 'virtualenv', 'source'):
        run('mkdir -p {0}/{1}'.format(site_folder, subfolder))

def _get_latest_source(source_folder):
    if exists(source_folder + '/.git'):
        run('cd {0} && git fetch'.format(source_folder))
    else:
        run('git clone {0} {1}'.format(REPO_URL, source_folder))
    current_commit = local("git log -n 1 --format=%H", capture=True)
    run('cd {0} && git reset --hard {1}'.format(source_folder, current_commit))

def _update_settings(source_folder, site_name):
    site_prefix = _get_site_prefix()
    settings_path = source_folder + '/superlists/settings.py'
    sed(settings_path, "DEBUG = True", "DEBUG = False")
    sed(settings_path,
        'ALLOWED_HOSTS =.+$',
        'ALLOWED_HOSTS = ["{0}"]'.format(site_name)
        )
    sed(settings_path,
        "STATIC_ROOT.+$",
        'STATIC_ROOT = "/usr/share/nginx/{0}-static"'.format(site_prefix)
        )
    secret_key_file = source_folder + '/superlists/secret_key.py'
    if not exists(secret_key_file):
        chars = 'abcdefghijklmnopqrstuvwxyz0123456789!@# $%^&*(-_=+)'
        key = ''.join(random.SystemRandom().choice(chars) for _ in range(50))
        append(secret_key_file, "SECRET_KEY = '{0}'".format(key))
    append(settings_path, '\nfrom .secret_key import SECRET_KEY')

def _update_virtualenv(source_folder):
    virtualenv_folder = source_folder + '/../virtualenv'
    if not exists(virtualenv_folder + '/bin/pip'):
        run('virtualenv --python=python3 {0}'.format(virtualenv_folder))
        run('{0}/bin/pip install pip --upgrade'.format(virtualenv_folder))
    run('{0}/bin/pip install -r {1}/requirements.txt'.format(
        virtualenv_folder, source_folder))

def _update_static_files(source_folder):
    site_prefix = _get_site_prefix()
    static_dir = '/usr/share/nginx/{0}-static'.format(site_prefix)
    sudo('mkdir -p {0}'.format(static_dir))
    sudo('chgrp {0} {1}'.format(env.user, static_dir))
    sudo('chmod g+w {0}'.format(static_dir))
    run('cd {0} && ../virtualenv/bin/python3 manage.py collectstatic --noinput'.format(
        source_folder))

def _update_database(source_folder):
    run('cd {0} && ../virtualenv/bin/python3 manage.py migrate --noinput'.format(
        source_folder))

def _install_init_script(source_folder):
    site_prefix = _get_site_prefix()
    init_template = source_folder + '/deploy_tools/gunicorn-template'
    init_script = 'gunicorn-{0}'.format(env.host)
    sudo('cp {0} /etc/init.d/{1}'.format(init_template, init_script))
    sed('/etc/init.d/{0}'.format(init_script), "SITENAME", site_prefix, use_sudo=True)
    sudo('chmod +x /etc/init.d/{0}'.format(init_script))
    if exists('/etc/init.d/{0}.bak'.format(init_script)):
        sudo('rm /etc/init.d/{0}.bak'.format(init_script))
    result = sudo('/etc/init.d/{0} start'.format(init_script))
    if result.succeeded:
        sudo('chkconfig {0} --add'.format(init_script))

