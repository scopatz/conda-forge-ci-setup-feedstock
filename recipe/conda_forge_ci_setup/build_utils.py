#!/usr/bin/env python

# This file was generated automatically from conda-smithy. To update this configuration,
# update the conda-forge.yml and/or the recipe/meta.yaml.
try:
    from ruamel_yaml import safe_load, safe_dump
except ImportError:
    from yaml import safe_load, safe_dump
import os
import subprocess
import click


call = subprocess.check_call


_global_config = {
    "channels": {
        "sources": ["conda-forge", "defaults"],
        "targets": [["conda-forge", "main"]],
    }
}


arg_feedstock_root = click.argument(
    "feedstock_root", type=click.Path(exists=True, file_okay=False, dir_okay=True)
)
arg_recipe_root = click.argument(
    "recipe_root", type=click.Path(exists=True, file_okay=False, dir_okay=True)
)
arg_config_file = click.argument(
    "config_file", type=click.Path(exists=True, file_okay=True, dir_okay=False)
)


def update_global_config(feedstock_root):
    """Merge the conda-forge.yml with predefined system defaults"""
    with open(os.path.join(feedstock_root, "conda-forge.yml")) as f:
        repo_config = safe_load(f)
    for k1, k2 in [("channels", "sources"), ("channels", "targets")]:
        if (k1 in repo_config) and (k2 in repo_config[k1]):
            _global_config[k1][k2] = repo_config[k1][k2]


@click.command()
@arg_feedstock_root
@arg_recipe_root
@arg_config_file
def setup_conda_rc(feedstock_root, recipe_root, config_file):
    specific_config = safe_load(open(config_file))
    if "channel_sources" in specific_config:
        # Due to rendering we may have more than one row for channel_sources
        # if nothing gets zipped with it
        first_row = specific_config["channel_sources"][0]  # type: str
        channels = [c.strip() for c in first_row.split(",")]
    else:
        update_global_config(feedstock_root)
        channels = _global_config["sources"]

    call(["conda", "config", "--remove", "channels", "defaults"])
    for c in reversed(channels):
        call(["conda", "config", "--add", "channels", c])

    call(["conda", "config", "--set", "show_channel_urls", "true"])


@click.command()
@arg_feedstock_root
@arg_recipe_root
@arg_config_file
def upload_package(feedstock_root, recipe_root, config_file):
    specific_config = safe_load(open(config_file))
    if "channel_targets" in specific_config:
        channels = [c.strip().split(" ") for c in specific_config["channel_targets"]]
    else:
        update_global_config(feedstock_root)
        channels = _global_config["targets"]

    from .upload_or_check_non_existence import upload_or_check

    for owner, channel in channels:
        upload_or_check(recipe_root, owner, channel, [config_file])


@click.command()
@arg_feedstock_root
@arg_recipe_root
@arg_config_file
def make_build_number(feedstock_root, recipe_root, config_file):
    """
    General logic

        The purpose of this is to ensure that the new compilers have build
        numbers > 1000 and legacy compilers have a build number < 1000.

        This is done by reading the build_number_decrement which is rendered
        into all the recipes.

        For linux and osx we want to avoid building for the legacy compilers
        with build numbers > 1000

    Example matrix
        - {'compiler_c': 'toolchain_c', 'build_number_decrement': 1000}
        - {'compiler_c': 'gcc',         'build_number_decrement': 0}

    """
    specific_config = safe_load(open(config_file))
    build_number_dec = int(specific_config.get("build_number_decrement", [0])[0])

    use_legacy_compilers = False
    for key in {"c", "cxx", "fortran"}:
        if "toolchain_{}".format(key) in specific_config.get(
                '{}_compiler'.format(key), ""):
            use_legacy_compilers = True
            break

    import conda_build.api

    rendered_recipe = conda_build.api.render(
        recipe_path=recipe_root, variants=specific_config
    )
    build_numbers = set()
    for recipe, _, _ in rendered_recipe:
        build_numbers.add(int(recipe.get_value("build/number")))
    if len(build_numbers) > 1:
        raise ValueError("More than one build number found, giving up")
    if len(build_numbers) == 0:
        print("> conda-forge:: No build number found.  Presuming build string")
        return
    try:
        build_number_int = build_numbers.pop()

        if build_number_int < 1000:
            if not use_legacy_compilers:
                raise ValueError(
                    "Only legacy compilers only valid with build numbers < 1000"
                )
            new_build_number = build_number_int
        else:
            new_build_number = build_number_int - build_number_dec

        config_dir, filename = os.path.split(config_file)
        with open(os.path.join(config_dir, "clobber_" + filename), "w") as fo:
            data = {"build": {"number": new_build_number}}
            print("> conda-forge:: Build number clobber {} -> {}".format(
                build_number_int, new_build_number))
            safe_dump(data, fo)
    except ValueError:
        # This is a NON string build number
        # we have this for things like the blas mutex and a few other similar cases
        print("> conda-forge:: No build number clobber gererated!")
        import traceback
        traceback.print_exc()


@click.command()
@arg_feedstock_root
@arg_recipe_root
@arg_config_file
def mangle_compiler(feedstock_root, recipe_root, config_file):
    """Try hard to break the compilers for osx"""
    # TODO
