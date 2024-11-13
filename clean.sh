rm -rf /Users/madhavajay/dev/syft/.clients/b@openmined.org/datasites/b@openmined.org/add
rm -rf /Users/madhavajay/dev/syft/.clients/c@openmined.org/datasites/c@openmined.org/add

rm -rf /Users/madhavajay/dev/syft/.clients/b@openmined.org/datasites/b@openmined.org/fedreduce/
rm -rf /Users/madhavajay/dev/syft/.clients/c@openmined.org/datasites/c@openmined.org/fedreduce/

mkdir -p /Users/madhavajay/dev/syft/.clients/c@openmined.org/datasites/c@openmined.org/data/
mkdir -p /Users/madhavajay/dev/syft/.clients/b@openmined.org/datasites/b@openmined.org/data/

echo "2" > /Users/madhavajay/dev/syft/.clients/c@openmined.org/datasites/c@openmined.org/data/data.txt
echo "7" > /Users/madhavajay/dev/syft/.clients/b@openmined.org/datasites/b@openmined.org/data/data.txt

rm -rf /Users/madhavajay/dev/syft/.clients/c@openmined.org/datasites/c@openmined.org/public/fedreduce/invite/

mkdir -p /Users/madhavajay/dev/syft/.clients/c@openmined.org/datasites/c@openmined.org/public/fedreduce/invite/add
cp ./add.yaml /Users/madhavajay/dev/syft/.clients/c@openmined.org/datasites/c@openmined.org/public/fedreduce/invite/add
cp ./functions.py /Users/madhavajay/dev/syft/.clients/c@openmined.org/datasites/c@openmined.org/public/fedreduce/invite/add
