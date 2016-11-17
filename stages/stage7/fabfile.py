#
# Copyright (c) 2015 Midokura SARL, All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import re

import os
import sys
import time

from orizuru.config import Config
from orizuru.utils import Daemon

from fabric.api import *
from fabric.utils import puts
from fabric.colors import green, yellow, red

import cuisine

def stage7():
    metadata = Config(os.environ["CONFIGFILE"])

    puts(yellow("adding ssh connections to local known hosts file"))
    for server in metadata.servers:
        puts(green("connecting to %s now and adding the key" % server))
        local("ssh -o StrictHostKeyChecking=no root@%s uptime" % metadata.servers[server]["ip"])

    #
    # network state database
    #
    execute(stage7_container_zookeeper)
    execute(stage7_container_cassandra)

    if 'physical_midonet_gateway' in metadata.roles:
        execute(stage7_physical_midonet_gateway_midonet_agent)
        execute(stage7_physical_midonet_gateway_setup)

    if 'container_midonet_gateway' in metadata.roles:
        execute(stage7_container_midonet_gateway_midonet_agent)
        execute(stage7_container_midonet_gateway_setup)

    if 'physical_openstack_compute' in metadata.roles:
        execute(stage7_physical_openstack_compute_midonet_agent)

    if 'container_openstack_compute' in metadata.roles:
        execute(stage7_container_openstack_compute_midonet_agent)

    execute(stage7_container_openstack_neutron_midonet_agent)

    execute(stage7_container_midonet_api)
    execute(stage7_container_midonet_manager)
    execute(stage7_container_midonet_cli)

    execute(stage7_midonet_tunnelzones)
    execute(stage7_midonet_tunnelzone_members)

    execute(stage7_neutron_networks)

    execute(stage7_midonet_fakeuplinks)

    if 'container_midonet_gateway' in metadata.roles:
        execute(stage7_test_connectivity)

@roles('container_zookeeper')
def stage7_container_zookeeper():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    puts(green("installing zookeeper on %s" % env.host_string))

    zk = []

    zkid = 1
    myid = 1

    for zkhost in sorted(metadata.roles["container_zookeeper"]):
        zk.append("{'id' => '%s', 'host' => '%s'}" % (zkid, metadata.containers[zkhost]['ip']))

        if env.host_string == zkhost:
            # then this is our id
            myid = zkid

        zkid = zkid + 1

    args = {}

    args['servers'] = "[%s]" % ",".join(zk)
    args['server_id'] = "%s" % myid

    cuisine.package_ensure(["zookeeper", "zookeeperd", "zkdump"])

    run("""

cat >/etc/zookeeper/conf/zoo.cfg <<EOF
tickTime=2000
initLimit=10
syncLimit=5
dataDir=/var/lib/zookeeper
clientPort=2181
snapCount=10000
autopurge.snapRetainCount=3
autopurge.purgeInterval=0
clientPortAddress=%s
EOF

""" % metadata.containers[env.host_string]['ip'])

    zkid = 0
    for zkhost in sorted(metadata.roles["container_zookeeper"]):
        zkid = zkid + 1
        run("""
cat >>/etc/zookeeper/conf/zoo.cfg <<EOF
server.%s=%s:2888:3888
EOF

""" % (zkid, metadata.containers[zkhost]['ip']))

    # if there is only one server in the ensemble make it the leader of itself.
    if zkid == 1:
        run("""
cat >>/etc/zookeeper/conf/zoo.cfg <<EOF
leaderServes=yes
EOF
""")

    run("service zookeeper stop; service zookeeper start")

    Daemon.poll('org.apache.zookeeper.server.quorum', 600)
    time.sleep(15)
    Daemon.poll('org.apache.zookeeper.server.quorum', 600)

    for zkhost in sorted(metadata.roles['container_zookeeper']):
        run("""
IP="%s"

for i in $(seq 1 10); do
    echo ruok | nc "${IP}" 2181 | grep imok || sleep 10
done

echo ruok | nc "${IP}" 2181 | grep imok

""" % metadata.containers[zkhost]['ip'])

    puts(red("TODO status check for 'not serving requests'"))

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_cassandra')
def stage7_container_cassandra():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    puts(green("installing cassandra on %s" % env.host_string))

    cs = []

    for cshost in metadata.roles['container_cassandra']:
        cs.append("%s" % metadata.containers[cshost]['ip'])

    cuisine.package_ensure(["openjdk-7-jre-headless", "dsc20", "sharutils"])

    run("""
uudecode <<EOF
begin-base64 644 /etc/cassandra/cassandra.yaml.bz2
QlpoOTFBWSZTWfDpJDQAC2p/gHkYEAB6///9P///+r////5gOEDoaffe7qtP
NMQdsAEqoUBIbU1AAB71x3tqI++8K996+vZW+5nsHHQyQH267bQAoBtpXFKa
GCN3ZDqmyZ2LY0AMU23LuoyqlJFXbQAKKUOtbZbDRKBmDQtNRdoAZpUKYBs2
1FDtpbJtECt4aaICMQIAhqYjE0Eaj1PSaH6o9NQyD01HqZPU9IA1PQCCCEAI
Kj2lNtTU2RqHqNpADTQAAABpo1TVHpANDQxAAAGg0ADQAAAACTSRIBEyaCA0
qb1HpNqanpPUD1PKDEANqAAAESkyFPQNUfqQ2QKZMmjRk0BppoA0MgAAAJEQ
ICBNTBNACYjRT1PSZNPRMQ0AAA0NNgEwgRChQIOG7Bf8faYdUnD7zm68yw+M
+h9bOESK+ILSHT53Ce90HG8eN33RvghupL7fw98aUp9zZ++mdllhpYU9oE3i
j/OPjEP6iFAead7uKog7P7qHlAlsNjIktS3UV29VDtqj241eonUNiCoi+mz4
O2/CH4xIYfkVu6w7W0T8zpS05y/zZ8Vvo64B4G6y2Nnxb1ekKLr5/kp+WeHT
3DG69ht8vGf4Nno4jxwWmMNXy+ep9Sn82t8moXb8cc5CQHI2wzcnc2wxFpcr
ShAKoPdrWLlNVHFyOTBwWPYyM9QQUAJJVQsVVARR3znfSyzbi7hPCkBzg1uE
2bqXmpLM480ZLjz0CmHCV1BTBXA7l1rOuMHfWoeYaxxlbH0eTLAywlxKy76+
Bibb9OW2/SIkzbVAe0oBWCT7/Z/KwqKyi8kj7V+XsngRneR7r49N661+R/GH
gHG1ayNdnRWVbibKNdYR1DE3ju4cscMr9TU0qsmo6WmjeNlppdOIyMMIOaAy
poibCJ7qMOYpwkpNTtuXTyKAHFNO2DgZRRp4iHVi9TLYdwEj+mkdeuD7OXDT
v02OuiimuKg70TUgSBEgwgyBGCnsyGalJ8Ex12w2B4YBUUgfbeiSnu9vaGuD
g82w0PUWuTDO3G8OPCIvmzK9HL0uUVmwVntc/7PVTJaK5EENQYpSi4eidKxH
nfEoXMkT+dhuVbGKs8ortL5eDvCMIqEG4jCH7WT0FimVdsmc+pUkXEoyc8U5
VKu0eHZSzSfhAeNYWz4svg/r3P6D3cESHmlvJwwe0FF+bMTpk/efv1/U14/P
di5NMBWqHmD1fF5Yaynu2aev8PXRonPdlYZ1vIYbd/P7KGnUKYwU7lQEdoUH
m/hf2Yz7Ca1FbyQFVQTyKgsu2egnmOAemguncjRte7rfu4XvQdz1FxzbBkGF
iNrVIJA4uq/QvKge0pDpLfOF9No7jv/deWHKDKlAy6E5G2XkgUU/TcXYDlYC
/kCJ0rbag4b+3cMF+ehFsEIRRGSpbaN75T0LOW9YXLcbeX8fom5pliHQfH4/
euSHIAg9xn9SOC6Hf9gbjtUoOMQqP6B3UIXQ9CE6GJR+hVoQvP0sSil9LL96
4Bv+U4LuWvVNWvDPn6qOwDr4OlUXO+g49FWT4z/XJ1wuDA6teuTlRYCO7F0u
WevBBjdsBlPOtn2x4KtZvZags9SnI0dc1XKJ+dq7EvnvGFeeTr4EFlVRkom5
XZyiVYZGimIiW0YPOX2bCzxh+fMdhIHEILKbKiWCwigiflzZcfPZc8iBqNDj
PzWCPVsaZNc9uL+7elrhOzcFyCSydzqdWxJiTW7+hlXzc8CPZoMo+j4fJ4aI
QIVY3WVEBU2WyvE9+82BffhMvwc2NgvFw5R0fYfglGfv80HbL/S1uuGfpiDT
dApsO/jsR6HDoOpDZzARLR7Bt4pKlsbbO7Ci9Nc51c8oJzgmad1NCox1doGy
1d9NDuS34m1ZCOLWHZhptoJ9c6XEbsaPflARcEijhsUSA/ggQjnrS8TtcMh9
+U4KFrDJgr3Hp2pRvp+VV98cNObTKaxkCm+chDjIpq/Uc+ICRQlQUGV7+O3R
u5htrdR8lHc46vi4tXH1n14xHJesNnB3mBd12NygQdG72nwWQNhnlRJQ5v7Y
40IFhRCA4IS37noIgdBBsiXynGomfzeDuCRtdJ4ROBnhYFAGxMP19I2jGMO3
XKakaSrtal0oDChd6Yw/j0U7xY67me1Hco+QVXaiivuNLnSuG278qP3y5uDj
fPPDZbu4omEJhbYPwzgBqiR1QVj0C+osOZKxbqQub2WAuVdJ4+nnfxxF+cbF
F20HWJMYZV25un1Qxodrr1RAt9ZcOko5XF24V5QVTKKf6BuruCnHVb6XkYvW
RCEg7rf3eaamo2V9mEOGDGNIM7CrOGMZisq3wiDpG7KkD10sSNF0fQYbQblD
GF2eC5zwrxksOGqbCs71XMhxs8QcLD+fZDC4i1luza5PLSrZ37VvAfN/vZT3
vjHuBCCE4LC4gvm17ZGBAfyL/jCeGQ6KuaUluL+T2YPnFNkAocQh9Oq9rz17
HR82Vdh5VkdjIEuvQ4jZeydFAzGPozEYVKTxUBCoHW8EOfx/GcuD1gjhFUVJ
buhpPh4mY9Jybr1CrTIKrxs6U6XBnGU9OCMQk3pjQf60VuMMNi5NJ2dfX0W8
ztVhC15LNXgC/2YjnicemJXb0QIW0RyQBjfj5LFBchQ/xi4v0OeoU9xu9281
HXDhIPt69BrtfvvQjecSpIpIOyBosbMvabKOxID9IHF4vW1Lbo3VmzioZBbs
cERD92FtBDIW7S9J5Zwjo3BYlgYlI4YKH11ebdTPR9J0hM8covGEiaey2T4F
lMLARlt4JwrOCh7iln0fA2/LIHMpN7tI7dwHQL6NMa6KN+a0BSuw3L260ocL
2jcTQlouaYgx55+T89b88gMNVs9ZrXtSDPigINrIjrH9ITBxsmSzbFiW/RQR
jmIt2VBBHW7UO9/qWSpwlkI+7+V1+cINkyhqyrlsNRjySTJoF1VAog+wInow
m/EPn87SurJECl6FU0Hpg6OgVjArwf1uuKQ/WRicKH5VgzHHRMfiH2z8/lXv
qwTov/O4SKt9mYkJnqgCijLlrswKmqQc+MdUHOUeVq8LhAy3CTJlFR08ud3y
uWObIGErsQrNn32tq1SYar4Zqou4xDrYOga3VRMgfd9TMTceHW7ea3Xr9Qut
z1S8hkDVqQyzPJNsJcE9T0LCUDm90E5RFCWcTYO2hNli8hej9KnaFwyqeuGH
dm62wLILnO+/zbXmgY7XE423u+3cZ5q0uy8ylrOqLnOAiIe5eazvd1RL5IQi
Gi97W6WhjYYUQNkFCMohb1t6uFM7GWFuU0PRIZDaYV7ujzTq9MxZguVNxb2R
MYrTU5sxnpiC2sjgsRpcjRaOteHKhXkZRPtrxnnYhgXkJ8gZs9C7sEOniuFQ
uXM4go1yy8t60IccC7R2wHBxGllBDr2pfbblCclGu+oWgmS2dJGD3uGdVYOl
kJPCjRLwGzqmruKrrywZnjq3WNv7HqS+RfdF2ROydNI2yC4kdC1ovZqUa64Z
Mi3iFzupRWAVBhpAM5azZgWUVuWkOvDQtN8Aao1GKLxFcuuJ76qsPFtmu4Da
PRbPumwGOM1vdIvW+3B3jDvMvKDSkXl0lgEFyvA3iVbAeEzWaK5yR+VqOLpG
F0oTd+J6O1Z2jnOeTVybpsOc4MOVqhy5gOL3jpOLpQJuOboGbAuVzVavqClw
tIcAhBeXEQ0C8JeRgzcOAautDD2gMUSxl2pkqAPXpoHbLlkgEIvCK4w3qyyw
eeAeO6thyulb2311Z7KiIQSD+DILaIooMIpAhuoUDSpYFu4j495FPf099xl0
PaeedGBDqibo4ET3VxF+aXyRGfhFDFVxplBGxEA+/vSA0aZd1wthsuRpGOqC
cMuJBdcv8OT41SEXTFNR7X3Hfz51IgjrdLD2A6EbelPqevJPbAh0ldQO9amc
kYPe4Sp7RQaAuDsVQBNaXugBRnNClwcfYLyWQhCRCI8L9DQ+6ZaLfNI4aAb2
7Km3/Cv2ZHiSrDtelA0uR0Y4fqJnxwvg2GF1w0oMffK3x4N7GgoI8LpYSvUq
NNOxC9UtNN6MuxPZSAt0urZuoL096YvK3D1ChNK1aI5lApShUYvHyVIgrjcz
sU7UO4KQMogHEZBCjcIy26tYRKZvAtTImkvxVxkuuYyt48/D7RXDqXYPdtSU
5gD5RUCR8sWRB88QCjABSSREkEQAMZJUkBGQhBboLQgpIN0KEAevDWfF6RT0
HP3OI6LCcWHRz82XAkbhosQx9hRERdmwiKr2+L3+bywSv1qSZ2BA4HDqh1ud
63UyH6fSrqj7MpjH6PXSQFYt8boI08czKUdhv2W42Y9hge29RwV2Fd0O+MGi
GgSzQZQ9X5CkRBHQhlgQQru035a8FOlKQp+VJl7qnvHho+r75iWpOZWNSmld
w8n0LbTrdm2iI+Rj8RHy859rEMbHEKQQT5iESJAIeo0mD7sekRR+Cn6Wjoy5
cYiOeuUvVcYpMKrAxg1RgTX/wf0uPuBUPpFX19eqsG+PKNXQWdPNuUxJOc81
shGF9dH1M4UqZK64xBEREL8nL2zVZlQ+lcUaIxNxfCUa7U36Ei/KBcGqr+NX
x26NL56MrynOM2+h9lCQHXuIucgJ0VGr67jzpJS6V1pXOXaDzWXkht1llWqQ
M8LTWn/JqPm6O2UbFQnNaZwiHRD44Sh5BvIHIqSvuYXWoPAhbaADklQKADvM
J73wGcIeAfrckuOqhgn+3eOYlIX+MD9iDaH/ovXt6AwrgB1o2YPLX9OWOkRD
VvRzwNuOIDL2Va6IG0NFKJLc9VmRBIkWuI2eNNWLSmSWImOLCQIBAOlDNVs3
K8IW5gF/r1etKnZHtvOEn8OC8jny4O3U7VLzuT9cENCMP9iUQL8zWz6fSDfm
Z8II2brLZrMgbiYbCwBnnHmKl2g1r4k9nS0TMR1JJfRPPkW3kZw5zRZ3pJ9w
yUD7OF4aNnQUpdINW75Z0WuKpQSWj1d/T6+s9nrICPqRBT3xCYN/FkP6vxO3
00p6PAzGOpS3xgpVRdU9Pw0YiQWa2IsQ9dvcfWUpkcuzb4aBcOO1zGpa2MyC
S2wUl26C+AXDlA72GJ3fUu42n8P4gvwFevf3/wR+n+pARPJ7HdVqeX6fPxY2
P49Z9+pZHnvJvoPogfJy9Ekqf7ATmFuIjJmOMXrwkNcEJ4FAe4LCiwaBALUo
LDQ7pjY5Ef2qm/5bHOR+ih4br9XjRuRDSebbS/mlDtNBkuIUEEYSEXoiSIt0
dQIlms9awQRHroB7nTpr/dK7CGVaTuVM0bAa0OSEyNVqyd/wtB3wDmM/Vg2S
GzddT6mBCF6rnX1QjyYdjWMoF63zIzMMBFAjADEgD3G/UoRKlPZ9SjePwHT0
W/1ou7XM+P+2G8ACA6ogDzk/Prb1al9XtXnB2CICogkDD0Lh292V3wb8xc87
RU1hGbbA7KVHTOvrA/AhHuvB5NYDcL5olns9/r/V2r7IoPOqhwqJCUwvfe0Q
wbNgnI7EDfSQkfFDy6qJrYfx2KHbPbNncz3c3NbCh1eSkRhpzX2hPFT2nSn4
P3+SXcJ3hKf6p++/kz6J62yfBhAx09nlJeq9bP9mHLtOfIoSLzV+9lFVCa/i
Af/hB3V9nOwgP3NL8GC9jSIYRsenbf7vAulfyUB6EYgWOuX3C8Zwr7nVR008
SPm8BCECFgM52QgQL0dSOWr4aSnj9CngCHZ8XzYFfMd8yDDI+QgLoClWhrCe
U4ccwccutUnESIolSITzHgiwROnGikstqC6VhBaNuDmo1SlJhlOPO5TKiKSU
RPYpVE3KCFkoiSBBnfhV8ySrY6LOmaLH7RtwZHOBXnLSOtFWaWkh1r95JCWo
rTcZ2Bzgs28YJLK+4RkSlGA0b5xtOmUV1hclWstFjQKlc2luzXe4SYCW+KcI
qHLrMTAyKMoOhEGaYoWW2tRDVbAyXjXudzTsMpYkGtbZQi2J2RSjPzSS+Drf
Ee4rPK12zJEbb01MywtYgoNgluhSquF+dFbwKbU4QDco2UiFIzgUXcOvI5oJ
1vd+1zJvCxyGbZKhD9tO8w/Rk9D5+R1akBRZ0s2fyMX9FCm9CL3MORmkFikM
jPYu5GHvTvp0W9cKk8H3g6SJ49R4DT9pO3HAIP1YnyPh/DhTtcHCu0Sms0cg
ygSeC4FQ/FrFabDMNbAw2bY2Eb0ofEKnV82ks1mbvlJyOsWF1xxy3BVCQBw6
Q6HD77KK1K2xxqIcTANk+hb3WHsyoosbSPuZrCtfjo0+qdzrzD9TPmxNiD9b
QrtUYGPGIXxYeXLmIS2yW7sirPXyKqhnIcmpQHgY6wotvGlkUUAy4pZ4ZetI
dtrnYlt1XnFQ87tw9DgkCGgTz2yEfNrs2hDxW5/Nlz2Gk0fRpgyF046+aLmT
0fBuAgEx9098gUJcQbgO/qFraqDluxXD2ghjENIGsiWeTqLkNXv6WZ8JClz/
F6pttdWlDY0UZVyxsYwJOaEFBnALDFnvxL9j8iAcrQVVhE8jC2JYLwhjmyDM
QRRgGbr/6VVhLFlZoypz4piJ9iI7sP1xko9TYFg7hQiF2q2/NULJ2ud6IQh1
k/SlGnL57i6P+79QgL5CWT+cYGIMU3PhPghD8RESL6NeUDR9s+KZCaG2w+JX
AcmnPwlBy5VJj5QhTGBkQS0AuUYj4CpCcQXPE1cLmlpIjJDGSGxJYhqH7t5M
nmsoHLJ5m6GDDyRmFBHwbY2WiElIeej5x6phYiAk8ntze95bctNJry4zWrfr
zjkH6zlNTWhLGRHkxnIesA82B2gKwY5ORflcHJJiH/wS7bNw9rJ7P8qeYGE7
Tg8CoPayIIqoqHlyV+Emnax3aP9hMEcPhdUw0KxGDKP08t7DoIpt/DonUvwO
zu1BFsXtTDMoOJcimNqNatzIB6dzrDckgxO59yxUWQsOGAvgL248Q79y6Id9
hrmBwm0lViDg4hoBf7SB4nvpDoDAqc4gVPU57yIIcb9ckqosWSGS0U+xwSRG
H+yn7db3WvOLBAmz42FVRohpdeka6Ef72irSttGdOgqAUDKKHJFFpRQ93M2i
z1iVWZaMnvRQqsiLWi7pRBUxoIxYz6dzIbOjCZQwM2cyjMgtREXgpUxJmX4U
mMEBkDbTUxyKKrBDo4mLGq5vWQGabbtNamZGDYGuLtwm94W1rgmHGjjWjLiQ
zdKLAqFtilRBiqaYhaOspp1FCgliqqrhdJJoaU3qLrgHfDcEMgga2ZM4Hlnu
s12pIP11V98pu5TYerazDs8Zk39Wj7cSMJGQpdmkiwjGk2gdwdKRBzfIHUQu
1oLjNGGfkdDGZuc2Xqm7Cpb0ikYwUjo9me2yevTkG4PCVd9yNWRoYtamA2X2
MhINeEAdXrrqD5ZkyauSwsmiUNjaYdzJkSSwkE6MvcqC+meesYa0UqOilaw6
0nuGSHKGpwMjZce3uIG2DtGcBoz3/PlBb7JUQSdbDf90aXplkkn8iBE/EJXZ
LiAGZNROLKXaWxIZzstz0hDvT6cBsh/VreBoi1FZjNKdmuy5NWNwmUCALUDc
xsZEaTcTG0CNxlCFKwFRQMbv8xl5Ik2Egja13zJ4M4aQZYhLJhnrlGlFDEm7
t7xO9isKFw9sYrnirQAQdJG1uWVJWmRTEg7o6hCN9Lo2ZObKFg0gosCrLgpc
bwGAM6GggRlmDzjjtmYQ2rNs3y1eKTtfWaINtLSrsrpCOI0sgvKDJAB4fIzo
++92BIiGvY552YLCDh4awYMHS1yGeFtBtmEt0ZAKuTFI/LCFissENhkuRZOZ
SzEUyaoVmIs1l9BMepreaNc83ugGHAgwVB/ZVRUPDoOgNhvlgu4CxTEIVo6l
ygcViBAd7KIsHdqC7Mp2DiISRGcP1RLjUzkQ22zsNTpFrDww1setLnaLt0F3
to56TuoaAiEcF8FCac5VapkcZ1KiUPuCgBcJZriUGZtTdcbaFehjgwzZZ0tS
sLQ4SbQ0TEXCSHygMwYw3Y3cyKK6MhmQZOxYniQau1MYSk0zr5kKmbxSBDwQ
oGkk2ARvmg+6yWdSwxgnWilJtSvvYzmLCuZ8hEYpUDGK+Y+kYiK1oZUEWJrL
QTdHyJVr0JvPlzI8zvdMIGhHYKPJ9rXtC57dc+IfGCq9Z8/LN9hrKZXFzEuo
0yOEAbI0OqRojpN0MoFJLIOBHFZ3gz5GwUcJW6cdtMxnHDKKLqMrAC9HsmeB
gCGsuCA6JYUnlJDpP0q5bOxKWh6XyGdfavq2lQ85N+ze/MRZBjAYyajlDs1T
iW+2TM3QqXRKpW5lA2F+DyXM1K9DmQGRmxxWRYM2c8rGaLs9g150ZrSKJLNd
08yYQKeffRoDfIfePhcDq9Teb1W5cwuaTMEU99mjZTaOQyEc/g4nttEgUbIz
ZdcyM0W9cm/clSNoWEXZiAvw2fJQRBiDWlGT3tYkVAbUsOyBpFKrF+IAyynL
UzzIXwsUHm4HeFDcwQqW7QkS7AkGWM1KBgyZyYSHViBsSvy9q0F8eOPJO9Xt
opLhF7sNjqy+6dmuXRCjI5GcTEE5GczW8p5FzluXYIlaZ2lX0kqmaTR0tNWH
CqiWkDe72UjTYQlcGoZRnCBS5kwirRCSs4rekTSpFFicySRZFcCltIlZNsWN
DIqg54gbQNyMQzrxI8wwDcssditXjGu9LUcVnuyq5TyvgFDJLIfaMU7dGB3v
LH+M5/N2DhE47Dr387pIa63efe2HStETjxkBFSUys8cYDC+74S+FQ4xsLkhw
RRQhcYVrqGBXvh4xxe9dLx5O+hjrji3hKmDNzQkyAfihOAR6WHZylFmeDDIf
FlT49L1Pj5RGtQn3JApwOZiEXezTfmHVkMGVIN0iIpvrv2mQElCOQo7djPLM
4tGw1kyxRLYNeAG26LV7mSNuS+yVAkA6kSxDWDnByiB85CROwvRCeX+Skiny
YVKwQTMq4xRpRc1QhmqEtiiiIsldazqH2bw1J5Hcn0iHkkPzeioHSSB+jnD2
cYpvKpv9nF7Q+AS7F71Q2sKrKmI1khByExA2QLMhB9jAkYICUuCUVILyqlSE
lA7pGhmtBnH2M4k4Jx1iqKDbISskUAUiIoEOEJWB1AbZSWCgcQ0LvZd1bFSl
toCfXbnKRhRs/S8/IJzJLx0k2UGUDGNkuXQjpXmuCxEwxneqhdfJDpTpEUTz
+OCwxCqlzMMUZFI2wuZXIoVBa20rWwSI1gk6Hy1JrIe0slAMkAQloREh/Uik
bYUYVhKkBFBEZK1AojEilQiKIWlJBYDGLUKyKCgWNRQWQqVohVtSE9+qfKzs
GHQVkhwfTdh+jIxbSNpcQD0ZIImOC1zNwjOo8Q4uykhmGzfIy5Xtz/QIXWxk
VRVgqRFhFBZIiGG4US8QMhLA+xDARiZSEpWFfOBkIHDFY8QYEJpFA51A9bO9
qgZWVzII3PXCPSrF5p7lALw6nDeVJQ0WzpR1Z6UrHooTvEquMF70RHiMgZCa
RoeD7dwRcvsV1JRfrELjEkwWsm/RwVHwxQzV2G70mkdE9EikM8ai41Yo553E
LTVWCzL3SIo5ZiK9/1D6NS099AoXQUOSx6WDRXnZsbD86ZR0Pcla67Wg8pIA
Sxgs6jUZEDZrEPTbtr6TBtApQqpvkE14ZD4p2fRkmrZJiB31cvxIH0SBs+SW
hqzAK3S2CgYZyXO3iy41sMscOm+3OIhX0KB2eB2fCiHXz8WdoUoIS5sz/mah
KJF8eOdaUwb+mGvoxf23h9bShZRc76gF7MhCiWAk3HsuvclU51nPKNaZml3L
4RjAsQte/mLMjCkIYqLT6NXdqJwgk7lA4BAs4Q1vfqU2U3IcGqucFogQUrKg
SoDGLBZKgWTT/TOv1BdZO33DlNAqcHe9+L2w6d+BR5bOfWjIjIEgoiiggxRg
futYjARFRRRiigqAqRgMBBZGApk6JBEU+D+H3HO3IGiFD1Z8xNfydZx+MaLF
8qqBbsPfSCsKdygrMJYeLVUetLdiVOx0QNCgoC93aQqD7bivR5wcKpLnFQR4
axwURzTOcPblQ1OSa3rcTp0OKNKA2kPRJ9xkLUtVSXoXhi97EjeaJE+O/LhO
i4K7K3PTJyrQztXMGtqGRf930hn58oN5J3ht6BwM1GSaUVESJS/aNBAxesft
DJYuZKsG21JDqa4srWqxEAYinNCiH1ylmZdCGM1Biyc0mZYoaVKKgbS++6yq
uxpQ2izOIwqHr8nbqqboWiNQHnJnN1RYY3ro7DJBQZDXU+qM7IHzHi2GtzWQ
NofF4zaYNOMclg+NFimH5HEL5HD++JPHlpFtWGdIMNK5oKDObpYY2IlUW+UL
oXziFwzRqOcKWT3qmFKCyKgbCRfMnnzpp8O7VNTTSWJ5+Dz91c0ehqgfV5Ty
QZ1g2CIVhOaYwqYmEUy0RxsBVH9VzJZGXAH0mLNCaRijAQGSG3eU+efHy6mS
dupsiveyEvB0XGjbQ4heTQSPiG0grJudqlRIfCIpPmGbhwPq1APUIHqwDuCQ
CiKiv3IVQVCqMtc4cR0PGaHWIM62VAcl0T4P1iJSptAotylWqA6I6W0OLoEN
lKWBSJMSzxqLRUw9S1k1NHkeppJzg84UgP2xvNGZQeAu8/fCKntaF+RhtQFE
JCwjc6sUtaFZiVk0Q8ro1e/Kb+AeHnANM8fts7fb/ZTqD1WCZ3ymYScd7LKc
u9DJqlHz7mbNcMPbPPDc4dEOc7oxYkMaEHmzG/BDMoQOcMCHggdZTqTJucIS
LhYFkRIzOqnWW7SSgcE58SyedkDtDmahyvTabax6dLjBFgz+pNemjWgrsdZi
o7s1QqVorhVRZWqcJjgI6bua+3VE0Viy8+LnGbMoDrKWXM26mrpctFyWUwuI
jW4LXLQ3a5dLcXOdxmVvGZEzbKKLVLMTFHExF4YZlAxlyyaQTL3NaNB0YbQk
QTkUNfvVRS0gw7nmq78D6hx8pO3L8WHJh6c9UskBuEYergNCCAqUaKUR+1Wm
fyNKEieJJywYNoBpkNJP9DCq4gsHRtw0kcmZlpZgzKU0Shl0QQ92jCEmhGiG
kih72s8TX3kmoj8/K7IU5hyNMl0mQNj95ULHMN4BVDqTAi6SbSEmyIISCxQn
QCvTJHyhZ30UsOv6T4IwZENE58FXkerD5dfTkvCAJuD5Bj2Vn1NQwGB2qD5j
ANRnofUGCPXSNjMPjFJUtsqA2yq1UtKLWHVArB7l8blmoXNFhGTWa1GBVSjY
MlGKGkIxDSiWFUaKCKB7IiSgyaKBNkZuMMTRzbNAysikWRU0xh0816ppa+YE
wGRnON0DfEOEexOSAbot0IfUyf0JiSc2H1pDDmUrDSTh2bsMZjCGCswCjBFm
gYMzxBe/W168MlAeoMoz9ac8L/dqJTkygzaEzDpkQ5Tpvv4ENYh0QkVaBTiL
0vEE4RDn5ypdGGsNkbELz+S1Lcj+T4hx5CTOHyhmZs4GiGdLooDDiWGd8OYi
kNHbCXfq3preBP6GSAe02rBWCqwFAUUi9bQVERYRBjab7SEHFiSyGFLAHvuo
QWP387dJg9TbbTISOIGyJiucmAXC53BgK7QiOxx4AOk8HU2ak/m3OiD2IMCw
QWUnyYoy4H6tJaW2sSf3mpBRgokcHMFhRMQrbTATIJg20BccRJP1oF9gN/xI
fVJ21OIX15f0mpmDPYZRFm3S2MKFISltGAM1IcjwQs0FwV1uWbocgRtIVl7E
0IqyIjnqw4gJ0D+HB1etCp+6+eSeZEZEetLBO374wz8Q8eM9AiuTl6pYHxYf
7fuigKSKKCkBT7+RxuAw5NHVgNoMe51HCa52GihkCnyuR35sac4gPa4XCAH5
1nLWlQysH4P9jmwlYz7Z1YcBDIn1Q2GLggDPWWGM6YChqZEbSGm1qDUB2Gny
+z2KFy8IV6lE0XZSzmEMsiYuNqOoAwWvISVY/T10CWP9DmSBH2vup9GErTMr
ySDieAVA+j/Fr0jMuO8DKVCQX2s2Ssj+Frd0EWHUHzIpKPi1zkDfHDtCwV4U
3rU/6rGz41WTGgIAowpenipDc0D78xUG0ygyBQEAWvYMgsvpPeN7v8tVkNct
I3HqaMKZEXeEHQIm0gWYVhjF2dGUobV43VIQkSIdeOWL0odZrkcsVC3aupsJ
SraMJNdsVUGIsjFiKqRUVGLKNKy21VBIKg2hUVixRgrbRvLMIjIRHMuAsEXL
YhGCKWlAVIoHdlVxCijERRZNWigKRaNYOpowxREZphD5Eh9EkUSMB8X4vNxj
6y6UAZ/Zn9CFsZd8GEBkH0jzZVd8i47OtFiG0oD2uw/rysik+IgUYjBmrW2+
txwbRtEVkthaNpacfhTM3kMiOJZtv1zsayTSR4lJxE3wnyBW2FPOz3/Ghplt
Jfynpr0kn5AUifz5T3rurwSMiOCOV5FrwI5cJCfg0uW+JMqjaSgNCK3xJQKK
d6Pbgca7XU+SuHAzQ3VdZHnAMIaZylEc0cUjZIqBDE6HI5rJOjLNrRIuXrlw
CHeXiiDP6JLMayRhGRqVEFGFzlSH8WtGJBTkZaUsqSpJ85zO6Q7h7hLXdG1U
uaYQy3BcUEhZJGWvaRQDIaUEnxH82Q0asPg7Eij6+sAT1kqUW2T2ZMykqlyZ
21WFGIMFhFWaHIMwA0jMDzCckGfJLAwhOEYV4RMIhwmmMhqGJ8EiIPy49kjv
4z0KUbr5fVv5qFfdeyzW7GH8ns+XdUcfSuWzuk2DmSmEsMKyZWpiTVvW+N0b
Tg4LOFzxrfgr2vPt88r2NG0wX4+SaScHjcLWKoDDAcShsxuEKBUSCaPK2EQj
bohswNicBnWYQglUDnHLlzjdUMibyElJFO9mYyMCbqwCTqgwkpJLoOSNyIhE
BIJ0EF6ddqRyxsxVAjGXSzFCwdfLUEM2x0X4FxXDjOCcN/IEdzIHJtdmduSO
CILkkWJG2UBRdmu6b4QqLiLFlEWaVZCSyEMhZ3VkYgggoFMU8sJiyQCISVhZ
DMXWzsjgoDINt90FncmKTDinS1zXD2QTvzlmpUjMKEIVNow/u4R/uqyhkoYj
MMbkOpAmGIUpUwHZDdcKXQbYb4K1lFIcaVi3erMEILphOvbhVfkBU8jaRRyZ
DOxOtiYSomOlYkIMr/q7IosGJUaEhxBHgUI8JQSCSYeQNHRnkwVmqM+SgUBO
h9YHh9lhe2snfRcaypT30/UyocBreGrl8OqneugtEXbYb1Lt0vDQ0iSvuGNn
BiomsMOUEFsyPc/Fq4HIrK2Ys8oKZcmXpRoCtfCQydPVNs80qfjB5OnUD4yc
5JOfRepFZoBiLhDbJD9LogK+a6KJLcSeiCxTIcxk2vnawQfgIsHizPXrh3I+
BRUGbOMh1YnFBJYSl7vJFLRsspSDEC2ykJE/awMMs8EMh5eNnKezCyTlyT5X
ma907OcFt2WicamYPDQbqmsLCW1QRhSrYichrMaMGW4F0plMaB0WiJDzhhDz
ed+PQU43jhYJZUNJ1QOvY8SHZFFMekhsnIzyDPCWQQ1n5YZWKWv2lh5AIAMX
GfA/ZO2pPanUKgV20gurOGs7i+/24j5XUPF4GAoCqpLk2Rx8XCulSMhpRQrp
o+dZdD+dbPWgFWik2KoJcYUYXUMBImzJbLIrMLM5g23ZVQsjw1wNJgPZLZRU
U3ZAc8JGizjKpjShXsqXhFovqWqEKEPQbYsdWm03nGxDuHE1hLolnKF0gJ6h
qhDZHKIKQBaZUGKzIgQgdNQBKrfZVVhQwBSMrIFS2xcyNmUPk5R0GhgVDpKt
JRWAZBoezCzLcORSJk6kNejZqzCHOjwla5gJTGnZO6ThbWojUKIuiTIfhH3r
ZVUwBmuFTcO+xJibD9nOdchODqU5PYOvc4VKljFigKyvY+Xx9GYMIZSyWCkK
a3AQB0QehDnFOraQ0vcWYFHlJBJvJPhWqngDNGZJHQYeElKsZqy1mU6OZTi8
zVGaUFQRTocz1ySc902mZN6JMwMY0TlwCVcvrKXFMXuylLUSPmxedhCE9yQ0
Acu8fQoeQxBmwWGitAkTcJaw+CHIy4KioMYMn3IUT6MKRnT3+8YzkKCeUEA0
CYw9I8B1YYAZs+uVljbppJXFanSihtFWNl1llVVZYcqAYXOmGsObWClbm6C4
5TMsMWIcqcGyFNbGxXLmRLmbTIzxDB4knGlZARQ6STkEOPrbs8sXVl7QCCkk
PJAh3V8inpKZGMHia9DUwjGRnBeg6yLIBINDeQRuBusGJlsTmpUdIhYDGTAK
WjQ6YVhooYQffaA8RmTHi5dtr08XSa0zPY9+G0ffaiCnpacN4iI44p2XmV2Z
QUCgGUXzJIQmkrIzyYyutkDEwkuNptI6tKWSmqdE8hCXv6/ubezZuyvaXiH3
kZ2M9AoCHhiwvMtwrOoUtkE7Ql+QPsc/Fe2elLk16YouzZBS8NMYq4I+YxQk
0gyOrBfmGhttFg5I185qHXXcFBohpUQyQGiGB1PMRS7+YwVx5X6B8yux2NUj
omCaGLRXwTGQzI4TRkm444shCCSA6QAsjFqbkt6hSWB4g40MHkMV+u9o4Jg1
f2S0WLAwiGnl2kPzYwUwbQxtkWnNorsefTNYMi5qKt2d6mADsP5ZTj7xBYzv
EsrZ45UwNNI2WiCMjIoJPAInXWzGauZS0BxhhymGJwLFybnGyTZuVilNb6YU
1OODkhFi0I+jQFRShox45GpQ+WqIFg7kqksfsYUM3A84AX0aR1xyUpL5MEGa
wYn0MAmit75EYRUskOAaCvwgu02Ns2hXBHO3YuCo/hCn8WijEwO10UgEJUaR
wOi3Z4knhMemqiTwjJyxuZCKUwkWgsXxeJoNn3FVV5UxEFyszd28L3oGeGOG
oVlhQVpHtdgiIsoCPRndcUbaJvimHew4t7Icb7XMTVmZact0zSpJpFialakq
bA4TpTBuGQdoCx2AfexIckyUrlCEkCS8IcpAKAQDqZhnoiwoaDioFaD/F3JF
OFCQ8OkkNA==
====
EOF
""")

    run("rm -f /etc/cassandra/cassandra.yaml; bzip2 -d /etc/cassandra/cassandra.yaml.bz2")

    run("""
SEEDS="%s"
ADDRESS="%s"

sed -i 's,%%%%CLUSTER_NAME%%%%,midonet,g;' /etc/cassandra/cassandra.yaml
sed -i 's,%%%%SEEDS%%%%,'"${SEEDS}"',g;' /etc/cassandra/cassandra.yaml
sed -i 's,%%%%LISTEN_ADDRESS%%%%,'"${ADDRESS}"',g;' /etc/cassandra/cassandra.yaml
sed -i 's,%%%%RPC_ADDRESS%%%%,'"${ADDRESS}"',g;' /etc/cassandra/cassandra.yaml

""" % (
    ",".join(cs),
    metadata.containers[env.host_string]['ip']
    ))

    run("service cassandra stop; rm -rf /var/lib/cassandra/*; service cassandra start")

    Daemon.poll('org.apache.cassandra.service.CassandraDaemon', 600)
    time.sleep(30)
    Daemon.poll('org.apache.cassandra.service.CassandraDaemon', 600)

    run("nodetool --host 127.0.0.1 status")

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

def stage7_start_physical_midonet_agent():
    run("""

service midolman restart

for i in $(seq 1 24); do
    ps axufwwwwwwwwwwwww | grep -v grep | grep 'openjdk' | grep '/etc/midolman/midolman.conf' && break || true
    sleep 1
done

sleep 10

ps axufwwwwwwwwwwwww | grep -v grep | grep 'openjdk' | grep '/etc/midolman/midolman.conf'

""")

    stage7_mn_conf()

def stage7_start_container_midonet_agent():
    run("""

for i in $(seq 1 12); do
     ps axufwwwwwwwwwwwww | grep -v grep | grep 'openjdk' | grep '/etc/midolman/midolman.conf' && break || true
    sleep 1
done

ps axufwwwwwwwwwwwww | grep -v grep | grep 'openjdk' | grep '/etc/midolman/midolman.conf' && exit 0

/usr/share/midolman/midolman-prepare

chmod 0777 /var/run/screen

mkdir -pv /etc/rc.local.d

cat>/etc/rc.local.d/midolman<<EOF
#!/bin/bash

while(true); do
    ps axufwwwwwwwwwwwww | grep -v grep | grep 'openjdk' | grep '/etc/midolman/midolman.conf' || /usr/share/midolman/midolman-start
    sleep 10
done

EOF

chmod 0755 /etc/rc.local.d/midolman

screen -S midolman -d -m -- /etc/rc.local.d/midolman

for i in $(seq 1 24); do
    ps axufwwwwwwwwwwwww | grep -v grep | grep 'openjdk' | grep '/etc/midolman/midolman.conf' && break || true
    sleep 1
done

sleep 10

ps axufwwwwwwwwwwwww | grep -v grep | grep 'openjdk' | grep '/etc/midolman/midolman.conf'

""")

    stage7_mn_conf()

def stage7_mn_conf():
    metadata = Config(os.environ["CONFIGFILE"])

    cshosts = []

    for container in sorted(metadata.roles["container_cassandra"]):
        cshosts.append("%s:9042" % metadata.containers[container]["ip"])

    #
    # since 1.9.1 (and OSS 2015.3) all runtime config is hidden behind mn-conf
    #
    run("""
CSHOSTS="%s"
CSCOUNT="%i"

cat >/tmp/cassandra.json<<EOF
cassandra {
    servers = "${CSHOSTS}"
    replication_factor = ${CSCOUNT}
    cluster = midonet
}

EOF

mn-conf set -t default < /tmp/cassandra.json

""" % (
    ",".join(cshosts),
    len(cshosts)
    ))

    #
    # haproxy needs to be turned on for L4LB
    #
    run("""

cat >/tmp/health.json<<EOF

agent {
    "haproxy_health_monitor" {
        # zookeeper://midonet/v1/config/schemas/agent: 62
        "haproxy_file_loc"="/etc/midolman/l4lb/"
        # zookeeper://midonet/v1/config/schemas/agent: 63
        "health_monitor_enable"=true
        # zookeeper://midonet/v1/config/schemas/agent: 65
        "namespace_cleanup"=false
    }
}

EOF

mn-conf set -t default < /tmp/health.json

""")

def stage7_install_midonet_agent():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    puts(green("installing MidoNet agent on %s" % env.host_string))

    zk = []

    zkc = []

    for zkhost in sorted(metadata.roles['container_zookeeper']):
        zk.append("{'ip' => '%s', 'port' => '2181'}" % metadata.containers[zkhost]['ip'])
        zkc.append("%s:2181" % metadata.containers[zkhost]['ip'])

    cs = []

    csc = []

    for cshost in sorted(metadata.roles['container_cassandra']):
        cs.append("'%s'" % metadata.containers[cshost]['ip'])
        csc.append("%s" % metadata.containers[cshost]['ip'])

    cuisine.package_ensure("midolman")

    run("""

ZK="%s"
CS="%s"
CS_COUNT="%s"

cat >/etc/midolman/midolman.conf<<EOF

[zookeeper]
zookeeper_hosts = ${ZK}
session_timeout = 30000
midolman_root_key = /midonet/v1
session_gracetime = 30000

[cassandra]
servers = ${CS}
replication_factor = ${CS_COUNT}
cluster = midonet
EOF

cat << EOF | mn-conf set -t default
zookeeper {
    zookeeper_hosts = "${ZK}"
}

cassandra {
    servers = "${CS}
}
EOF

echo "cassandra.replication_factor : ${CS_COUNT}" | mn-conf set -t default

mn-conf template-set -h local -t agent-compute-medium

cp /etc/midolman/midolman-env.sh.compute.medium /etc/midolman/midolman-env.sh

""" % (
    ",".join(zkc),
    ",".join(csc),
    len(csc)
    ))

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('physical_openstack_compute')
def stage7_physical_openstack_compute_midonet_agent():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    stage7_install_midonet_agent()
    stage7_start_physical_midonet_agent()

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('physical_midonet_gateway')
def stage7_physical_midonet_gateway_midonet_agent():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    stage7_install_midonet_agent()
    stage7_start_physical_midonet_agent()

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('physical_midonet_gateway')
def stage7_physical_midonet_gateway_setup():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    run("""

ip link show | grep 'state DOWN' | awk '{print $2;}' | sed 's,:,,g;' | xargs -n1 --no-run-if-empty ip link set up dev

ip a

""")

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_openstack_neutron')
def stage7_container_openstack_neutron_midonet_agent():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    stage7_install_midonet_agent()
    stage7_start_container_midonet_agent()

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_openstack_compute')
def stage7_container_openstack_compute_midonet_agent():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    stage7_install_midonet_agent()
    stage7_start_container_midonet_agent()

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_midonet_gateway')
def stage7_container_midonet_gateway_midonet_agent():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    stage7_install_midonet_agent()
    stage7_start_container_midonet_agent()

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_midonet_gateway')
def stage7_container_midonet_gateway_setup():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    server_idx = int(re.sub(r"\D", "", env.host_string))

    overlay_ip_idx = 255 - server_idx

    run("""
if [[ "%s" == "True" ]] ; then set -x; fi

#
# fakeuplink logic for midonet gateways without binding a dedicated virtual edge NIC
#
# this is recommended for silly toy installations only - do not do this in production!
#
# The idea with the veth-pairs was originally introduced and explained to me from Daniel Mellado.
#
# Thanks a lot, Daniel!
#

# this will go into the host-side of the veth pair
PHYSICAL_IP="%s"

# this will be bound to the provider router
OVERLAY_BINDING_IP="%s"

FIP_BASE="%s"

ip a | grep veth1 || \
    ip link add type veth

# these two interfaces are basically acting as a virtual RJ45 cross-over patch cable
ifconfig veth0 up
ifconfig veth1 up

# this bridge brings us to the linux kernel routing
brctl addbr fakeuplink

# this is the physical ip we use for routing (SNATing inside linux)
ifconfig fakeuplink "${PHYSICAL_IP}/24" up

# this is the physical plug of the veth-pair
brctl addif fakeuplink veth0 # veth1 will be used by midonet

# change this to the ext range for more authentic testing
ip route add ${FIP_BASE}.0/24 via "${OVERLAY_BINDING_IP}"

# enable routing
echo 1 > /proc/sys/net/ipv4/ip_forward

""" % (
        metadata.config["debug"],
        "%s.%s" % (metadata.config["fake_transfer_net"], str(server_idx)),
        "%s.%s" % (metadata.config["fake_transfer_net"], str(overlay_ip_idx)),
        metadata.config["fip_base"]
    ))

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_midonet_api')
def stage7_container_midonet_api():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    zk = []

    for zkhost in sorted(metadata.roles['container_zookeeper']):
        zk.append("%s:2181" % metadata.containers[zkhost]['ip'])

    #
    # slice and dice the password cache so we can access it in python
    #
    passwords = {}
    with open(os.environ["PASSWORDCACHE"]) as passwordcache:
        for line in passwordcache:
            name, var = line.partition("=")[::2]
            passwords[name] = str(var).rstrip('\n')

    cuisine.package_ensure(["midonet-api", "tomcat7", "sharutils"])

    run("""
uudecode <<EOF
begin-base64 664 /usr/share/midonet-api/WEB-INF/web.xml.bz2
QlpoOTFBWSZTWWqZORIAAa3fgHIQcBf6lT//3/C////wUAP9einZrwhex2oS
hIyNART9GpP1R6j1B5JsUyD01PUzE1GQBBUbU9TJ6jEZANMmgBkAMEA0MgSK
gRqfpT9U9IyaZqaANAAADIAMgikqekP0aoGjJpiAAABoAAABIkJMjSelPAU8
KHqbaoDIaPUaDQAaFrKgUbmKBB9oAW/SRZjogkCo+ckRk8be1UiK9T8L61z+
rq30leFFVPZ40MOt28IQBpnYwdxyoUYfdJD/rHCSMAkj8E6JtsmJIcH0vqNy
k9mmeenmXzTeD7+mPTrMEzAJWqF7rnHlFhEQk6Gska3Zk5qWfvPM0pjcdbyh
tBZpiiIbcbKLqVs3swagvRx5Zva+R63wU1y9izcWxY1MHMRj84yaJSjJ5gEe
qi3KyJIlFM/HgkiQCk7WkjHBNASaLqERVOppI9QAq7thFxwY0ry9Jxdh1tu3
R1cqYce2VtsudO/lKm+5MhlxGtNmq/410+DX0XOoj5y9Gu4YWvoOieSFg8LT
9SQkrYhNKn6WDyCESorConVICSIhtncA5qYkDV0G2zqGsUFqiQ7+FkiKUHOd
xorWzo8TlmrIhnUtt4eXtnLRJzpKUeSc3M7JhFOuRnCZvIOjSv3gEkYRCArS
QqOl5BCQ74XCCANaDck/1DiojH+TFiG9ZOZbZLq0yg4C5E8ANW2/VJF6SM4T
CvHXpk8syVpXZASC0whCipadaC42XFmwuRAmAm0mNtMTTSGJsaKJ3M2x4Dks
RfpMorzL5IlC8KFRM3FjaGNtZXK3LElJjNinMdCHqlIS4duFY046UUkiu2xH
din1sQ006iBEssz6KKRjtv8gXVB3DRvBrlERnSxGA4oP8mS+RQ52YjuU1se8
99wW5tW7UBp0ILcBNFAxmTXPxmlW1bIbzqq5RWhMSRhGCSJjEkOd5EkkKl1x
Su4eUKcLNkWQ5SZBlGYpRMqWEEKOVEiEMKKKpAhWaNcGvHOlzS6kUUSDlghp
EgdMwkhsMHGK0qOHNnuxpDAScnMjPi+2rGG8qYAGFSBS8KlkHhMcJrCs8A8F
8xdL72GhVZ1AG08z9Jy6eObthFgg5mBlagQgL5TZHXBBQ1BkMhtZUFAbKDS4
7QpzwUp3QHurxczNS1jsK+JUFiHXD3TRYQkOngz6upswiIKGJaI0zyPaeZrR
a1QdYAwqFo5VK0nFZbo2Su1qVTZhcKqjVZlBU8gppZFuqrPiSctz1gsIZZIC
Ig5awgqNocm6h6VasoAkRTXqkphupT/F3JFOFCQapk5EgA==
====
EOF
""")

    run("rm -f /usr/share/midonet-api/WEB-INF/web.xml; bzip2 -d /usr/share/midonet-api/WEB-INF/web.xml.bz2")

    run("""

sed -i 's,qqAPIHOSTqq,%s,g' /usr/share/midonet-api/WEB-INF/web.xml
sed -i 's,qqAPIPORTqq,8081,g' /usr/share/midonet-api/WEB-INF/web.xml
sed -i 's,qqADMIN_TOKENqq,%s,g' /usr/share/midonet-api/WEB-INF/web.xml
sed -i 's,qqDOMAIN_NAMEqq,,g' /usr/share/midonet-api/WEB-INF/web.xml
sed -i 's,qqKEYSTONE_SERVICE_HOSTqq,%s,g' /usr/share/midonet-api/WEB-INF/web.xml
sed -i 's,qqKEYSTONE_USER_NAMEqq,admin,g' /usr/share/midonet-api/WEB-INF/web.xml
sed -i 's,qqKEYSTONE_USER_PASSWORDqq,%s,g' /usr/share/midonet-api/WEB-INF/web.xml
sed -i 's,qqZOOKEEPERSqq,%s,g' /usr/share/midonet-api/WEB-INF/web.xml

""" % (
    metadata.servers[metadata.roles["midonet_api"][0]]["ip"],
    passwords["export ADMIN_TOKEN"],
    metadata.containers[metadata.roles["container_openstack_keystone"][0]]["ip"],
    passwords["export ADMIN_PASS"],
    ",".join(zk)
    ))

    run("""
cat>/etc/default/tomcat7<<EOF
TOMCAT7_USER=tomcat7
TOMCAT7_GROUP=tomcat7
JAVA_OPTS="-Djava.awt.headless=true -Xmx128m -XX:+UseConcMarkSweepGC"
JAVA_OPTS="$JAVA_OPTS -Djava.security.egd=file:/dev/./urandom"
JAVA_OPTS="$JAVA_OPTS -Xms512m -Xmx1024m -XX:MaxPermSize=256m"
EOF
""")

    run("""
cat>/etc/tomcat7/server.xml<<EOF
<?xml version='1.0' encoding='utf-8'?>
<Server port="8005" shutdown="SHUTDOWN">
  <Listener className="org.apache.catalina.core.JasperListener" />
  <Listener className="org.apache.catalina.core.JreMemoryLeakPreventionListener" />
  <Listener className="org.apache.catalina.mbeans.GlobalResourcesLifecycleListener" />
  <Listener className="org.apache.catalina.core.ThreadLocalLeakPreventionListener" />
  <GlobalNamingResources>
    <Resource name="UserDatabase" auth="Container"
              type="org.apache.catalina.UserDatabase"
              description="User database that can be updated and saved"
              factory="org.apache.catalina.users.MemoryUserDatabaseFactory"
              pathname="conf/tomcat-users.xml" />
  </GlobalNamingResources>
  <Service name="Catalina">
    <Connector port="8081" protocol="HTTP/1.1"
               connectionTimeout="20000"
               URIEncoding="UTF-8"
               redirectPort="8443"
               maxHttpHeaderSize="65536" />
    <Engine name="Catalina" defaultHost="localhost">
      <Realm className="org.apache.catalina.realm.LockOutRealm">
        <Realm className="org.apache.catalina.realm.UserDatabaseRealm"
               resourceName="UserDatabase"/>
      </Realm>
      <Host name="localhost"  appBase="webapps"
            unpackWARs="true" autoDeploy="true">
        <Valve className="org.apache.catalina.valves.AccessLogValve" directory="logs"
               prefix="localhost_access_log." suffix=".txt"
               pattern="%h %l %u %t &quot;%r&quot; %s %b" />
      </Host>
    </Engine>
  </Service>
</Server>
EOF
""")

    run("""
cat>/etc/tomcat7/Catalina/localhost/midonet-api.xml<<EOF
<Context
    path="/midonet-api"
    docBase="/usr/share/midonet-api"
    antiResourceLocking="false"
    privileged="true"
/>
EOF
""")

    run("service tomcat7 stop; service tomcat7 start")

    Daemon.poll('org.apache.catalina.startup.Bootstrap', 600)
    time.sleep(30)
    Daemon.poll('org.apache.catalina.startup.Bootstrap', 600)

    #
    # wait for the api to come up
    #
    puts(green("please wait for midonet-api to come up, this can take up to 10 minutes."))
    run("""

wget -SO- -- http://%s:8081/midonet-api/; echo

""" % metadata.servers[metadata.roles["midonet_api"][0]]["ip"])

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_midonet_manager')
def stage7_container_midonet_manager():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    if "OS_MIDOKURA_REPOSITORY_USER" in os.environ:
        if "OS_MIDOKURA_REPOSITORY_PASS" in os.environ:
            if "MEM" == metadata.config["midonet_repo"]:
                cuisine.package_ensure("midonet-manager")
                run("""
APIHOST="%s"

cat >/var/www/html/midonet-manager/config/client.js <<EOF
{
  "api_host": "http://$APIHOST:8081",
  "login_host": "http://$APIHOST:8081",
  "trace_api_host": "http://$APIHOST:8081",
  "traces_ws_url": "ws://$APIHOST:8460",
  "api_namespace": "midonet-api",
  "api_version": "1.9",
  "api_token": false,
  "agent_config_api_host": "http://$APIHOST:8459",
  "agent_config_api_namespace": "conf",
  "poll_enabled": true
}
EOF
""" % metadata.servers[metadata.roles["midonet_api"][0]]["ip"])

                run("service apache2 stop; service apache2 start")

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_midonet_cli')
def stage7_container_midonet_cli():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    cuisine.package_ensure([
        "python-midonetclient",
        "python-keystoneclient",
        "python-glanceclient",
        "python-novaclient",
        "python-neutronclient"
        ])

    run("""
if [[ "%s" == "True" ]] ; then set -x; fi

#
# initialize the password cache
#
%s

API_IP="%s"
API_URI="%s"

OPENSTACK_RELEASE="%s"

source /etc/keystone/KEYSTONERC_ADMIN 2>/dev/null || source /etc/keystone/admin-openrc.sh

if [[ "kilo" == "${OPENSTACK_RELEASE}" || "liberty" == "${OPENSTACK_RELEASE}" ]]; then
    ADMIN_TENANT_ID="$(openstack project list --format csv | sed 's,",,g;' | grep -v ^ID | grep ',admin' | awk -F',' '{print $1;}' | xargs -n1 echo)"
else
    ADMIN_TENANT_ID="$(keystone tenant-list | grep admin | awk -F'|' '{print $2;}' | xargs -n1 echo)"
fi

cat >/root/.midonetrc<<EOF
[cli]
api_url = http://${API_IP}:${API_URI}
username = admin
password = ${ADMIN_PASS}
tenant = ${ADMIN_TENANT_ID}
project_id = admin
EOF

""" % (
        metadata.config["debug"],
        open(os.environ["PASSWORDCACHE"]).read(),
        metadata.containers[metadata.roles["container_midonet_api"][0]]["ip"],
        metadata.services["midonet"]["internalurl"],
        metadata.config["openstack_release"]
    ))

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

def add_host_to_tunnel_zone(debug, name, ip):
    run("""
if [[ "%s" == "True" ]] ; then set -x; fi

NAME="%s"
IP="%s"

/usr/bin/expect<<EOF
set timeout 10
spawn midonet-cli

expect "midonet> " { send "tunnel-zone list name gre\r" }
expect "midonet> " { send "host list name ${NAME}\r" }
expect "midonet> " { send "tunnel-zone tzone0 add member host host0 address ${IP}\r" }
expect "midonet> " { send "quit\r" }

EOF

midonet-cli -e 'tunnel-zone name gre member list' | grep "${IP}"

""" % (debug, name, ip))

    run("""
if [[ "%s" == "True" ]] ; then set -x; fi

NAME="%s"
IP="%s"

/usr/bin/expect<<EOF
set timeout 10
spawn midonet-cli

expect "midonet> " { send "tunnel-zone list name vtep\r" }
expect "midonet> " { send "host list name ${NAME}\r" }
expect "midonet> " { send "tunnel-zone tzone0 add member host host0 address ${IP}\r" }
expect "midonet> " { send "quit\r" }

EOF

midonet-cli -e 'tunnel-zone name vtep member list' | grep "${IP}"

""" % (debug, name, ip))

@roles('container_midonet_cli')
def stage7_midonet_tunnelzones():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    run("""
if [[ "%s" == "True" ]] ; then set -x; fi

#
# create tunnel zones
#
midonet-cli -e 'tunnel-zone list name gre' | \
    grep '^tzone' | grep 'name gre type gre' || \
        midonet-cli -e 'tunnel-zone create name gre type gre'

midonet-cli -e 'tunnel-zone list name vtep' | \
    grep '^tzone' | grep 'name vtep type vtep' || \
        midonet-cli -e 'tunnel-zone create name vtep type vtep'

""" % metadata.config["debug"])

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_midonet_cli')
def stage7_midonet_tunnelzone_members():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    cuisine.package_ensure("expect")

    for container_role in ['container_midonet_gateway', 'container_openstack_compute', 'container_openstack_neutron']:
        if container_role in metadata.roles:
            for container in metadata.containers:
                if container in metadata.roles[container_role]:
                    puts(green("adding container %s as member to tunnel zones" % container))
                    add_host_to_tunnel_zone(metadata.config["debug"], container, metadata.containers[container]["ip"])

    for physical_role in ['physical_midonet_gateway', 'physical_openstack_compute']:
        if physical_role in metadata.roles:
            for server in metadata.servers:
                if server in metadata.roles[physical_role]:
                    puts(green("adding server %s as member to tunnel zones" % server))

                    #
                    # tinc can only work with MTU 1500
                    # we could use the approach from http://lartc.org/howto/lartc.cookbook.mtu-mss.html
                    # but instead we will disable rp_filter and use the physical interface ip
                    #
                    # server_ip = "%s.%s" % (metadata.config["vpn_base"], metadata.config["idx"][server])
                    #

                    server_ip = metadata.servers[server]["ip"]
                    add_host_to_tunnel_zone(metadata.config["debug"], server, server_ip)

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_midonet_cli')
def stage7_neutron_networks():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    run("""
if [[ "%s" == "True" ]] ; then set -x; fi

FIP_BASE="%s"

OPENSTACK_RELEASE="%s"

source /etc/keystone/KEYSTONERC_ADMIN 2>/dev/null || source /etc/keystone/admin-openrc.sh

if [[ "kilo" == "${OPENSTACK_RELEASE}" || "liberty" == "${OPENSTACK_RELEASE}" ]]; then
    neutron net-list | grep public || \
        neutron net-create public --router:external
else
    neutron net-list | grep public || \
        neutron net-create public --router:external=true
fi

# this is the pseudo FIP subnet
neutron subnet-list | grep extsubnet || \
    neutron subnet-create public "${FIP_BASE}.0/24" --name extsubnet --enable_dhcp False

# create one example tenant router for the admin tenant
neutron router-list | grep ext-to-int || \
    neutron router-create ext-to-int

# make the Midonet provider router the virtual next-hop router for the tenant router
neutron router-gateway-set "ext-to-int" public

# create the first admin tenant internal openstack vm network
neutron net-list | grep internal || \
    neutron net-create internal --shared

# create the subnet for the vms
neutron subnet-list | grep internalsubnet || \
    neutron subnet-create internal \
        --allocation-pool start=192.168.77.100,end=192.168.77.200 \
        --name internalsubnet \
        --enable_dhcp=True \
        --gateway=192.168.77.1 \
        --dns-nameserver=8.8.8.8 \
        --dns-nameserver=8.8.4.4 \
        192.168.77.0/24

# attach the internal network to the tenant router to allow outgoing traffic for the vms
neutron router-interface-add "ext-to-int" "internalsubnet"

SECURITY_GROUP_NAME="testing"

# delete existing security groups with the same name
for ID in $(nova secgroup-list | grep "${SECURITY_GROUP_NAME}" | awk -F'|' '{ print $2; }' | awk '{ print $1; }'); do
    nova secgroup-delete "${ID}" || true # may be already in use
done

# try to find the survivor
for ID in $(nova secgroup-list | grep "${SECURITY_GROUP_NAME}" | awk -F'|' '{ print $2; }' | awk '{ print $1; }'); do
    EXISTING="${ID}"
done

# if not found, create
if [[ "${EXISTING}" == "" ]]; then
    nova secgroup-create "${SECURITY_GROUP_NAME}" "created by a script"
    EXISTING="$(nova secgroup-list | grep "${SECURITY_GROUP_NAME}" | awk -F'|' '{ print $2; }' | awk '{ print $1; }')"
fi

nova secgroup-add-rule "${EXISTING}" tcp 22 22 0.0.0.0/0 || true # ssh
nova secgroup-add-rule "${EXISTING}" tcp 80 80 0.0.0.0/0 || true # http
nova secgroup-add-rule "${EXISTING}" udp 53 53 0.0.0.0/0 || true # dns
nova secgroup-add-rule "${EXISTING}" icmp -1 -1 0.0.0.0/0 || true # icmp

SSHKEY="/root/.ssh/id_rsa_nova"

if [[ ! -f "${SSHKEY}" ]]; then
  ssh-keygen -b 8192 -t rsa -N "" -C "nova" -f "${SSHKEY}"
fi

nova keypair-list | grep "$(hostname)_root_ssh_id_rsa_nova" || \
    nova keypair-add --pub_key "${SSHKEY}.pub" "$(hostname)_root_ssh_id_rsa_nova"

nova boot \
    --flavor "$(nova flavor-list | grep m1.tiny | head -n1 | awk -F'|' '{print $2;}' | xargs -n1 echo)" \
    --image "$(nova image-list | grep cirros | head -n1 | awk -F'|' '{print $2;}' | xargs -n1 echo)" \
    --key-name "$(nova keypair-list | grep "$(hostname)_root_ssh_id_rsa_nova" | head -n1 | awk -F'|' '{print $2;}' | xargs -n1 echo)" \
    --security-groups "$(neutron security-group-list | grep testing | head -n1 | awk -F'|' '{print $2;}' | xargs -n1 echo)" \
    --nic net-id="$(neutron net-list | grep internal | head -n1 | awk -F'|' '{print $2;}' | xargs -n1 echo)" \
    "test$(date +%%s)"

""" % (
        metadata.config["debug"],
        metadata.config["fip_base"],
        metadata.config["openstack_release"]
    ))

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_midonet_cli')
def stage7_midonet_fakeuplinks():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

    # provider router has been created now. we can set up the static routing logic.
    # note that we might also change this role loop to include compute nodes
    # (for simulating a similar approach like the HP DVR off-ramping directly from the compute nodes)
    for role in ['container_midonet_gateway']:
        if role in metadata.roles:
            for container in metadata.containers:
                if container in metadata.roles[role]:
                    puts(green("setting up fakeuplink provider router leg for container %s" % container))

                    physical_ip_idx = int(re.sub(r"\D", "", container))

                    overlay_ip_idx = 255 - physical_ip_idx

                    #
                    # This logic is the complimentary logic to what happens on the midonet gateways when the veth pair, the fakeuplink bridge and the eth0 SNAT is set up.
                    # We might some day change this to proper BGP peer (which will be in another container or on a different host of course).
                    #
                    run("""
if [[ "%s" == "True" ]] ; then set -x; fi

CONTAINER_NAME="%s"
FAKEUPLINK_VETH1_IP="%s"
FAKEUPLINK_NETWORK="%s.0/24"
FAKEUPLINK_VETH0_IP="%s"

/usr/bin/expect<<EOF
set timeout 10
spawn midonet-cli

expect "midonet> " { send "cleart\r" }

expect "midonet> " { send "router list name 'MidoNet Provider Router'\r" }

expect "midonet> " { send "router router0 add port address ${FAKEUPLINK_VETH1_IP} net ${FAKEUPLINK_NETWORK}\r" }
expect "midonet> " { send "port list device router0 address ${FAKEUPLINK_VETH1_IP}\r" }

expect "midonet> " { send "host list name ${CONTAINER_NAME}\r" }
expect "midonet> " { send "host host0 add binding port router router0 port port0 interface veth1\r" }

expect "midonet> " { send "router router0 add route type normal weight 0 src 0.0.0.0/0 dst 0.0.0.0/0 gw ${FAKEUPLINK_VETH0_IP} port port0\r" }
expect "midonet> " { send "quit\r" }

EOF

""" % (
        metadata.config["debug"],
        container,
        "%s.%s" % (metadata.config["fake_transfer_net"], str(overlay_ip_idx)),
        metadata.config["fake_transfer_net"],
        "%s.%s" % (metadata.config["fake_transfer_net"], str(physical_ip_idx))
    ))

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

@roles('container_midonet_cli')
def stage7_test_connectivity():
    metadata = Config(os.environ["CONFIGFILE"])

    if cuisine.file_exists("/tmp/.%s.lck" % sys._getframe().f_code.co_name):
        return

#
#    if not "container_midonet_gateway" in metadata.roles:
#        if "connect_script" in metadata.config:
#            if not cuisine.file_exists("/tmp/.%s.connect_script.lck" % sys._getframe().f_code.co_name):
#                cuisine.file_upload("/tmp/%s" % metadata.config["connect_script"], "%s/../conf/%s" % (os.environ["TMPDIR"], metadata.config["connect_script"]))
#                puts(green("running connect script: %s" % metadata.config["connect_script"]))
#                run("/bin/bash /tmp/%s" % metadata.config["connect_script"])
#                cuisine.file_write("/tmp/.%s.connect_script.lck" % sys._getframe().f_code.co_name, "xoxo")
#

    run("""
if [[ "%s" == "True" ]] ; then set -x; fi

FIP_BASE="%s"

source /etc/keystone/KEYSTONERC_ADMIN 2>/dev/null || source /etc/keystone/admin-openrc.sh

neutron floatingip-list | grep "${FIP_BASE}" || neutron floatingip-create public

FIP_ID="$(neutron floatingip-list | grep "${FIP_BASE}" | awk -F'|' '{print $2;}' | xargs -n1 echo)"

INSTANCE_IP=""

for i in $(seq 1 100); do
    INSTANCE_ALIVE="$(nova list | grep test | grep ACTIVE)"

    if [[ "" == "${INSTANCE_ALIVE}" ]]; then
        sleep 1
    else
        break
    fi
done

if [[ "" == "${INSTANCE_ALIVE}" ]]; then
    echo "instance not alive after 100 seconds, this is not good."
    exit 1
fi

INSTANCE_IP="$(nova list --field name | grep test | awk -F'|' '{print $2;}' | xargs -n1 echo | xargs -n1 nova show | grep 'internal network' | awk -F'|' '{print $3;}' | xargs -n1 echo)"

NOVA_PORT_ID="$(neutron port-list --field id --field fixed_ips | grep "${INSTANCE_IP}" | awk -F'|' '{print $2;}' | xargs -n1 echo)"

neutron floatingip-list --field fixed_ip_address | grep "${INSTANCE_IP}" || neutron floatingip-associate "${FIP_ID}" "${NOVA_PORT_ID}"

neutron floatingip-list

""" % (
        metadata.config["debug"],
        metadata.config["fip_base"]
    ))

    run("""

source /etc/keystone/KEYSTONERC_ADMIN 2>/dev/null || source /etc/keystone/admin-openrc.sh

FIP="$(neutron floatingip-list --field floating_ip_address --format csv --quote none | grep -v ^floating_ip_address)"

for i in $(seq 1 120); do
    </dev/null ssh -q -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=2 -i /root/.ssh/id_rsa_nova "cirros@${FIP}" uptime && break || true
    sleep 1
done

ping -c9 "${FIP}"

""")

    cxx=[]

    cxx.append('wget -O/dev/null http://www.midokura.com')
    cxx.append('ping -c3 www.midokura.com')
    cxx.append('ping -c3 www.google.com')

    for cxc in cxx:
        puts(green("trying to run command [%s] in testvm" % cxc))
        run("""

source /etc/keystone/KEYSTONERC_ADMIN 2>/dev/null || source /etc/keystone/admin-openrc.sh

FIP="$(neutron floatingip-list --field floating_ip_address --format csv --quote none | grep -v ^floating_ip_address | head -n1)"

</dev/null ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=5 -i /root/.ssh/id_rsa_nova "cirros@${FIP}" -- %s

""" % cxc)

    cuisine.file_write("/tmp/.%s.lck" % sys._getframe().f_code.co_name, "xoxo")

