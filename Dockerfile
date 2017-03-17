##
# NAME             : iadvize/language-tools-server
# VERSION          : 3
# DOCKER-VERSION   : 1.13
# DESCRIPTION      : Python runtime v3
# TO_BUILD         : docker build --pull=true --no-cache --rm -t iadvize/language-tools-server:3.2 -t iadvize/language-tools-server:latest .
# TO_SHIP          : docker push iadvize/language-tools-server:3.2 && docker push iadvize/language-tools-server:latest
# TO_RUN           : docker run -ti --rm -p 8080:8080 iadvize/language-tools-server:3.2
##

FROM java:8

MAINTAINER Samuel Berthe <samuel.berthe@iadvize.com>

ENV DEBIAN_FRONTEND="noninteractive" \
    INITRD="No" \
    PACKAGES="curl unzip" \
    LANGUAGE_TOOL_VERSION="3.2"

WORKDIR /app
EXPOSE 8080
CMD /usr/bin/java -cp /app/LanguageTool-${LANGUAGE_TOOL_VERSION}/languagetool-server.jar org.languagetool.server.HTTPServer --port 8080 --public

RUN apt-get update && \
    apt-get install -yq --no-install-recommends $PACKAGES && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app && \
    curl -L -o /app/LanguageTool-${LANGUAGE_TOOL_VERSION}.zip https://www.languagetool.org/download/LanguageTool-${LANGUAGE_TOOL_VERSION}.zip && \
    unzip /app/LanguageTool-${LANGUAGE_TOOL_VERSION}.zip && \
    rm -rf /app/LanguageTool-${LANGUAGE_TOOL_VERSION}.zip
