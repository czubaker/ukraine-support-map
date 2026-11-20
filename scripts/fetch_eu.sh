#!/bin/sh
# Download the latest HowTheyVote.eu open data release into raw/eu
set -e
cd "$(dirname "$0")/.."
mkdir -p raw/eu
TAG=$(curl -s https://api.github.com/repos/HowTheyVote/data/releases/latest | python3 -I -c "import json,sys;print(json.load(sys.stdin)['tag_name'])")
B=https://github.com/HowTheyVote/data/releases/download/$TAG
for f in members votes member_votes groups group_memberships countries national_parties national_party_memberships geo_areas geo_area_votes; do curl -sL -o raw/eu/$f.csv.gz $B/$f.csv.gz; done
curl -sL -o raw/eu/last_updated.txt $B/last_updated.txt
echo "HowTheyVote data $TAG"
