The v3-boba repository is a wrapper around several submodules which track
the upstream Erigon and Optimism Bedrock projects. It also pulls in the
current 'boba' repository to support legacy deployments and to simplify the
process of migrating tools into the V3 system.

After cloning this repository, follow these steps to build and launch a
local development stack:

> git submodule init
> git submodule update --recursive

Note that the Erigon and Op-geth repositories will pull in a large amount of
test data, so ensure that you have sufficient disk space (at least 18 GiB).

> cd erigon
> make && docker-compose build

This will create a Docker image named bobanetwork/erigon-base which is used
for building the Bedrock l2 image.

> cd ../optimism
> make
> make devnet-up
> cd ops-bedrock
> docker-compose logs --follow

The optimism Makefile also supports "devnet-down" and "devnet-clean" targets
which may be used to reset the system so that "devnet-up" can be run again.
It is also possible to stop and start containers individually using Docker
commands inside the ops-bedrock directory.

A utility script is provided to generate L1->L2 transactions (the other
direction is not yet implemented).

> cd boba_utilities/stress_tester
> python ./deposit-l1.py

Note that the local port numbers are reversed in Bedrock vs. our legacy system.
The local L1 is on port 8545 and the local L2 is on port 9545.

