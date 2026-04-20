FROM brainicism/bgutil-ytdlp-pot-provider

# Upstream image ships without libexpat1, which is required by the native
# `canvas` module that jsdom uses for YouTube Proof-of-Origin Token minting.
# Without it, POTs are generated in a degraded mode and YouTube rejects the
# resulting media URLs with HTTP 403.
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends libexpat1 \
    && rm -rf /var/lib/apt/lists/*
USER node
