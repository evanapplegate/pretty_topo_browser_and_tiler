export OMP_NUM_THREADS=3 OPENBLAS_NUM_THREADS=3 VECLIB_MAXIMUM_THREADS=3
cd /Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/scripts/6_site_tone
date
python3 -W ignore cluster.py rest 2>&1 | tail -1 | cut -c1-200
seq 2 18 | xargs -n 1 -P 4 sh -c 'python3 -W ignore cluster.py "$0" 2>&1 | tail -1 | cut -c1-260'
date
for i in 1 0; do python3 -W ignore cluster.py $i 2>&1 | tail -1 | cut -c1-260; date; done
ls ../../topo_finder/site/clip8_tm | grep -c 'jpg$'
ls ../../topo_finder/site/clip_tm | grep -c 'jpg$'
