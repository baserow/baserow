# Baserow CI/CD overview

# Background Knowledge

This doc doesn’t explain and assumes you already know:

- How Gitlab CI/CD works,
  see [https://docs.gitlab.com/ee/ci/](https://docs.gitlab.com/ee/ci/) for an intro
- How docker/docker-compose works
    - [https://docs.docker.com/build/](https://docs.docker.com/build/)
    - Including more advanced features like multi stage and multi platform builds:
        - [https://docs.docker.com/build/building/multi-platform/](https://docs.docker.com/build/building/multi-platform/)
        - [https://docs.docker.com/build/building/multi-stage/](https://docs.docker.com/build/building/multi-stage/)
    - [https://docs.docker.com/compose/](https://docs.docker.com/compose/)
- Bash scripting

# Quick links

- Our Baserow public repo CI/CD definition file can be
  found [here](https://github.com/baserow/baserow/blob/develop/.gitlab-ci.yml)
- Our shared CI job definitions
  from [here](https://github.com/baserow/baserow/blob/develop/.gitlab/ci_includes/jobs.yml)
- We have two CI base images used by jobs:
    - Any docker build jobs are run using this
      image [here](https://gitlab.com/baserow/baserow/container_registry/3961081) which
      is built using
      this [Dockerfile](https://github.com/baserow/baserow/blob/develop/.gitlab/ci_dind_image/Dockerfile)
    - Any non docker build jobs that need various utils run
      using [this Dockerfile](https://github.com/baserow/baserow/blob/develop/.gitlab/ci_util_image/Dockerfile)
      with those tools added
    - Push an MR with a change to either of the Dockerfiles and a manually triggered job
      will appear in that branches pipeline which will automatically rebuild and push
      this image

# Overview of how Baserow uses git branches

* `develop` is the branch we merge newly developed features onto from feature
  branches.
* a feature branch is a branch made starting off `develop` containing a specific
  new feature, when finished it will be merged back onto `develop`.
* `master` is the branch which contains official releases of Baserow, to do so we
  periodically merge the latest changes from `develop` onto `master` and then tag
  that new master commit with a git tag containing the version (1.8.2 etc).

# Useful CI features that devs should know

## Use commit message tags to change how the CI works

There are various tags you can include in your commit messages that change what
the Gitlab CI does.
* `[skip-ci]` will disable CI pipelines completely for this commit.
* `[build-all]` will trigger a full build of all images, including the prod variants, 
   all-in-one, cloudron for this commit.

## Trigger manual pipelines which let you control individual pipeline vars

Go to [this page](https://gitlab.com/baserow/baserow/-/pipelines/new) to trigger a 
custom one off pipeline for your branch, you can override any CI variables you want 
for this manual pipeline in the Gitlab UI making it great for testing CI changes etc.

# CI Overview

See below for the high level summary of the steps GitLab will run to build, test and
release Baserow images in various scenarios depending on the branches involved.

## Visual overview of CI jobs

For a visual overview of our CI jobs, which I strongly recommend you use, you can:

1. [Going to our pipelines page](https://gitlab.com/baserow/baserow/-/pipelines)
2. Open a pipeline on the develop branch
3. Switch `Group jobs by` to `Job dependencies`
4. Then enable `Show dependencies` to get a graph view showing how all our CI jobs link
   together.

## CI Stage overview

Our CI is split up into a number of stages, each stage produces artifacts (built docker
images, test results etc)
and passes them down to the following stages.

### Stage 1: Build dev images

First we build the dev variants of our backend and web-frontend images.

A dev variant of our image is our Dockerfile's build with the target being the
dev stage. Our dockerfiles are multi-stage, and when building a Dockerfile you can
pick a certain stage to build to. The dev stages of our images contain all the
dev dependencies etc.

> Why do we build these dev images?
> 1. We can use them to cache all of the python/node libraries so we don't need to
>    re-install them every time.
> 2. Originally when these pipelines were setup it was imagined it would be useful
>    to be able to download these dev images from the container repo and use them.
>    It turns out we literally never need to do this, devs always build their own
>    images. As a result we could optimize these CI jobs by instead of building a full
>    dev image containing all the code, just building a version with the required
>    libraries etc. (which can run very rarely) and then in the following test stages
>    mount in the git source code directly into the containers.

### Stage 2: Test dev images

Using the dev variants of the images (which were built and pushed to the container
registry by the previous stage), we can then use them to run all the lints/tests.

### Stage 3: Build prod images (only on develop/master or when `[build-all]` added to commit message)

Finally using the dev variants of the images as docker build caches, we build the 
prod variants of the images. 

### Stage 4: Publish images (only on develop/master)

Next we docker push the images to Dockerhub/our Gitlab container registry.

### Stage 5: Trigger external project CI

Finally, we trigger downstream builds who potentially want to use any new images/code
we've just built.

## Per Branch explanations

Next lets go into detail per branch and trigger of a pipeline what the high level
inputs/outputs are:

### On the master branch - When MR Merged/commit pushed/branch made

1. The backend and web-frontend dev images will be built and pushed to the
   gitlab ci image repo.
    1. A `{image_dev}:ci-latest-$CI_COMMIT_SHA` image is pushed for the next stages.
    2. A `{image_dev}:ci-latest-$BRANCH_NAME` image is pushed to cache future runs.
2. The pushed `ci-latest-$CI_COMMIT_SHA` images will be tested and linted. If a
   previously successful test/lint run is found for the same/prev commit AND no
   files have changed which could possibly change the result this is skipped.
3. Cached from the `ci-latest-$CI_COMMIT_SHA` image the non-dev images will be built
   and then both the dev and non-dev images will be with tagged marking them as
   tested and pushed to the gitlab ci repo.
4. Finally, we trigger a pipeline in any downstream repos that depend on this one.

### On the develop branch - When MR Merged/new commit pushed

The build and testing steps 1, 2 and 3 from above are run first and then:

1. Push the tested images from step 3 to the Dockerhub repo under the
   `develop-latest` tag.
2. Trigger a pipeline in any downstream repos that depend on this one.

### On feature branches - When MR Merged/new commit pushed

Only build and testing steps 1 and 2 from above are run.

### On the latest commit on master - When a Git tag is created

This is done when we have merged the latest changes from develop on master, and we
want to release them as a new version of Baserow. GitLab will automatically detect
the new git tag and only do the following:

* Push the images built from step 3 above (or fail if they don't exist) to the
  Dockerhub repo with the tags:
    * `latest`
    * `${git tag}`

### Older commit on master - When a Git tag created

We push the images built from step 3 above (or fail if they don't exist) to the
Dockerhub repo with the tags:

1. `${git tag}`

### Any non-master commit - When a Git tag created

We fail as only master commits should be tagged/released.

# Cleanup

Images with tags starting with `ci-latest` or `ci-tested` (made in steps 1. and 3.)
will be deleted after they are 7 days old by a job that runs daily at 11AM CET.
This is configured in
Gitlab [here](https://gitlab.com/baserow/baserow/-/settings/packages_and_registries/cleanup_image_tags).

# Docker Layer Caching and its Security implications.

The build jobs defined in `.gitlab/ci_includes/jobs.yml` use docker `BUILD_KIT` enabled
image caching to:

1. Cache docker image builds between different pipelines and branches.
2. Cache docker image builds between the build and build-final stages in a single
   pipeline.

By using BuildKit and multi-stage docker builds we are able to build and store images
which can then be pulled and used as a cache to build new images quickly from.

## When are docker builds cached between different pipelines and branches?

On branches other than master:

1. A build job first tries to find the latest image built on that branch
   (registry.gitlab.com/baserow/baserow/ci/IMAGE_NAME:ci-latest-BRANCH_NAME)
   to use as a build cache.
2. If no latest image is found then the build job will try use the latest ci dev image
   build on the develop branch:
   (registry.gitlab.com/baserow/baserow/ci/IMAGE_NAME:ci-latest-develop)
3. Otherwise, the build job will run the build from scratch building all layers.
4. Once the build job finishes it will push a new ci-latest-BRANCH_NAME image for
   future pipelines to cache from. This image will be built with
   BUILDKIT_INLINE_CACHE=1 ensuring all of its intermediate layers can be cached from.

On master:

1. The latest develop ci image will be used as the build cache.
2. Otherwise, no build caching will happen.

## When are docker builds cached on the same pipeline and how?

1. The initial build stage jobs will build and push a ci image (specifically a docker
   image built with `--target dev`, this means it will build the `dev` stage in the
   Dockerfile). This image will be built with BUILDKIT_INLINE_CACHE=1 ensuring all of
   its intermediate layers can be cached from.
2. This image will be used for testing etc if required.
3. Finally, in the build-final stage we build the non dev images. We cache these
   images from two sources:
    1. The dev ci image built by the previous build stage. This will contain all
       intermediate layers so the non-dev build should re-use cached layers for all
       docker layers shared by the dev and non dev stages.
    2. The latest non-dev ci image built by first a previous pipeline on this branch
       or if not found then the latest non-dev ci image built on develop. On master
       similarly to the first build stage we only check develop.

## Security implications of docker image caching

This article does a great job explaining why docker layer caching can cause security
issues: https://pythonspeed.com/articles/docker-cache-insecure-images/ . But
fundamentally if you cache the FROM base_image and RUN apt upgrade && apt update
stages docker won't ever re-run these, even if the base image has changed OR there
have been security fixes published for the packages.

# Periodic full rebuilds on develop

To get around the security implications of docker image layer caching we have a
daily ci pipeline scheduled job on
develop (https://gitlab.com/baserow/baserow/-/pipeline_schedules)
which sets TRIGGER_FULL_IMAGE_REBUILD=yes as a pipeline variable. This forces all
the build stages to build their docker images from scratch pulling any updated base
images.

This pipeline rebuilds all
the `registry.gitlab.com/baserow/baserow/ci/IMAGE_NAME:ci-latest-develop`
images used for build caching on other branches, develop itself and on master to have
the latest security updates.

## Morning CI job extra features

This morning CI job also runs more pytest test than normal by enabling tests flagged
with
the `@pytest.mark.once_per_day_in_ci` flag.

# ARM Builds

On the master branch the docker images built and pushed to Dockerhub are 
[multi platform](https://docs.docker.com/build/building/multi-platform/). Meaning
the same image can be run on ARM64 and AMD64 systems. 

This is enabled by the `BUILD_ARM` CI variable and `BUILD_ARM_ON_BRANCH` controls
which branch these ARM builds occur on. We set `BUILD_ARM_ON_BRANCH` to `master` 
as a performance optimization so `develop` pipelines run faster. As a result the images
that come out of the `develop` and feature branch pipelines only support AMD64. Doing
the ARM build adds approx 5-10 minutes onto the pipeline build.

The ARM build works by using 
[dockers build remote agent support](https://docs.docker.com/build/drivers/remote/). 
So we have a remote ARM64 server, which the ci build jobs will configure docker to 
connect to and run the ARM part of the docker image build on that server. 

## Why not use emulated arm docker builds?

As of last testing, it took 1+ hours to build a single image in a gitlab runner on
ARM so dedicated ARM hardware is really critical to do this.


# FAQ

## How new version of Baserow is released to Dockerhub

1. Create an MR from develop to master and merge it.
2. Wait for the merge commit pipeline succeed on master which will build and test the
   images.
3. Tag the merge commit in the GitLab GUI with the git tag being the Baserow version
   (1.8.2, 1.0, etc).
4. GitLab will make a new pipeline for the tag which will push the images built in
   step 2 to Dockerhub.
    5. If step 2 failed or has not completed yet then this pipeline
       will fail and not push anything.

## Why does master cache from develop and not use its own ci-latest cache images?

1. Master might not have any pipelines run for weeks between releases meaning:
   a. If it had its own ci-latest cached images they would get cleaned up before they
   could be used
   b. If they weren't cleaned up their layers might be massively out of date and weeks
   old.
2. Ok then why not have a periodic job to rebuild on master?
   a. We are already periodically rebuilding on develop, why do the same work twice
   if we can just cache from develop.
   b. Master might start randomly breaking if breaking changes appear in the base
   layers that get rebuilt. It's much more preferable that only develop breaks
   and we fix any issues there before they hit master.
3. Why not just always rebuild from scratch on master with no docker build caching?
   a. This makes the release process slower
   b. If a base image or package change occurs between the time we finish testing our
   develop images and when we merge develop into master, the images are master
   might completely break as a result. So now we would have to worry about
   this potential source of issues as an extra step for every release.
   c. We are essentially testing entirely different images from the ones being deployed
   if we just test on develop and master does a full rebuild.
4. By having develop being the only place where we do the full rebuilds, it means we:
   a. Test those rebuilt base layers on all the feature branches and during any
   develop testing.
   b. We CD from develop to staging and so these rebuilds are automatically deployed
   and tested by that also.
   c. Only have one source of these rebuilt layers, which we test on develop and then
   re-use on master knowing they are safe.

