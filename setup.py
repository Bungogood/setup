import logging
import argparse
import pathlib
import typing
import yaml
import os

quite = False
wsl = False

apt = "apt -qq" if quite else "apt"

log = logging.getLogger()
log.setLevel(logging.INFO)

def readYAML(path: str) -> str:
    with open(path, "r") as f:
        return yaml.safe_load(f)

# merges default into config
def merge(config: dict, default: dict, path=None):
    if path is None: path = []
    for key in default:
        if key in config:
            if isinstance(config[key], dict) and isinstance(default[key], dict):
                merge(config[key], default[key], path + [str(key)])
            elif config[key] == default[key]:
                pass # same leaf value
            else:
                logging.debug("Overide {path}: {change}".format(path='.'.join(path + [str(key)]),change=config[key]))
        else:
            config[key] = default[key]
    return config

def timezone(tz: str) -> str:
    return "timedatectl set-timezone {}".format(tz)

def install(packages: typing.List[str]) -> str:
    return "{} install -y {}".format(apt, " ".join(packages))

def post_install(commands: typing.List[str]) -> str:
    return "\n".join(commands)

def ssh(ssh_config: dict) -> str:
    out = []
    out.append("mkdir -p $HOME/.ssh")
    for key in ssh_config["authorized-keys"]:
        out.append("{} >> $HOME/.ssh/authorized_keys".format(key))
    if ssh_config["generate"]:
        out.append("ssh-keygen -q -t {algorithm} -b {key_size} -f {keyfile} -N \"{passphrase}\" -C \"{comment}\"".format(
            algorithm=ssh_config["algorithm"],
            key_size=ssh_config["key-size"],
            keyfile=ssh_config["keyfile"],
            passphrase=ssh_config["passphrase"],
            comment=ssh_config["comment"]
        ))
    return "\n".join(out)

def gpg(apps: dict) -> str:
    out = ["# gpg keys"]
    gpg_path = "/etc/apt/keyrings"
    out.append("mkdir -p {}".format(gpg_path))
    for name, config in apps.items():
        if "gpg" in config:
            config = config["gpg"]
            out.append("# {}".format(name))
            out.append("curl -fsSL {key} | gpg --dearmor -o {gpg_path}/{name}.gpg".format(
                key=config["key"],
                gpg_path=gpg_path,
                name=name
            ))
            out.append("echo \"deb [arch=$(dpkg --print-architecture) signed-by={gpg_path}/{name}.gpg]\" {tee} | tee /etc/apt/sources.list.d/{name}.list > /dev/null".format(
                tee=config["tee"],
                gpg_path=gpg_path,
                name=name
            ))
            logging.debug("adding {} gpg keys".format(name))
    return "\n".join(out)

def apps(apps: dict) -> str:
    out = ["# installing apps"]
    for name, config in apps.items():
        out.append("# {}".format(name))
        out.append(install(config["install"]))
        if "post-install" in config:
            out.append(post_install(config["post-install"]))
    return "\n".join(out)

def generate(config: dict) -> str:
    out = []
    out.append("{} update".format(apt))
    # timezone
    if not wsl:
        out.append(timezone(config["timezone"]))
    # install basics
    out.append(install(config["basics"]))
    # ssh
    out.append(ssh(config["ssh"]))
    # add gpg keys
    out.append(gpg(config["apps"]))
    out.append("{} update".format(apt))
    # install apps
    out.append(apps(config["apps"]))
    return "\n".join(out)

def save(path: str, config: dict):
    with open(path, "w+") as f:
        data = generate(config)
        f.write(data)
    os.chmod(path, 0o755)

def main(config_file: str, output_file: str) -> None:
    default = readYAML("default.yml")
    config = readYAML(config_file)
    config = merge(config, default)
    save(output_file, config)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a setup script for linux from yaml files")

    parser.add_argument('-i', '--config_file', 
        type=pathlib.Path, metavar="<config.yml>",
        default="config.yml",
        help="Path to config yaml"
    )

    parser.add_argument('-o', '--output_file', 
        type=pathlib.Path, metavar="<setup.sh>",
        default="setup.sh",
        help="Path to output script"
    )

    args = parser.parse_args()
    main(args.config_file, args.output_file)
