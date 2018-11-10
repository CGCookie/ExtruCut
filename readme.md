# ExtruCut

This is an example add-on that demonstrates how to use CG Cookie CookieCutter to create add-ons for Blender 2.79b.

## To Clone...

To clone this add-on example:

```
git clone --recursive git@github.com:vxlcoder/cookiecutter_bextruder.git
```


## Creating a Blender 2.79b add-on using CookieCutter

To create a new add-on using CookieCutter:

```
# create new addon folder
mkdir newaddon
cd newaddon

# initialize as new git repo
git init .

# add CC addon_common as submodule
git submodule add git@github.com:CGCookie/addon_common.git addon_common
git submodule update --init --recursive
```

To update the `addon_common`:

```
# update CC addon-common
cd newaddon
git submodule foreach git pull origin master
```

