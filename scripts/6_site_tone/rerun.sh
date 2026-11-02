export OMP_NUM_THREADS=3 OPENBLAS_NUM_THREADS=3 VECLIB_MAXIMUM_THREADS=3
cd /Users/evanapplegate/Dropbox/freelance/pretty_topo_browser_and_tiler/scripts/6_site_tone
date
printf '7\n13\n14\n3\n1\n' | xargs -n 1 -P 5 sh -c 'python3 -W ignore cluster.py "$0" wide 2>&1 | tail -1 | cut -c1-280'
date
