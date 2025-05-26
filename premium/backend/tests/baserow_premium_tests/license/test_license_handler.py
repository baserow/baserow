import base64
from unittest.mock import patch

from django.db import transaction
from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
import responses
from baserow_premium.license.exceptions import (
    FeaturesNotAvailableError,
    InvalidLicenseError,
    LicenseAlreadyExistsError,
    LicenseAuthorityUnavailable,
    LicenseHasExpiredError,
    LicenseInstanceIdMismatchError,
    NoSeatsLeftInLicenseError,
    UnsupportedLicenseError,
    UserAlreadyOnLicenseError,
)
from baserow_premium.license.features import PREMIUM
from baserow_premium.license.handler import LicenseHandler
from baserow_premium.license.models import License, LicenseUser
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from freezegun import freeze_time
from rest_framework.status import HTTP_200_OK

from baserow.core.cache import local_cache
from baserow.core.exceptions import IsNotAdminError

VALID_ONE_SEAT_LICENSE = (
    # id: "1", instance_id: "1"
    b"eyJ2ZXJzaW9uIjogMSwgImlkIjogIjEiLCAidmFsaWRfZnJvbSI6ICIyMDIxLTA4LTI5VDE5OjUyOjU3"
    b"Ljg0MjY5NiIsICJ2YWxpZF90aHJvdWdoIjogIjIwMjEtMDktMjlUMTk6NTI6NTcuODQyNjk2IiwgInBy"
    b"b2R1Y3RfY29kZSI6ICJwcmVtaXVtIiwgInNlYXRzIjogMSwgImlzc3VlZF9vbiI6ICIyMDIxLTA4LTI5"
    b"VDE5OjUyOjU3Ljg0MjY5NiIsICJpc3N1ZWRfdG9fZW1haWwiOiAiYnJhbUBiYXNlcm93LmlvIiwgImlz"
    b"c3VlZF90b19uYW1lIjogIkJyYW0iLCAiaW5zdGFuY2VfaWQiOiAiMSJ9.e33Z4CxLSmD-R55Es24P3mR"
    b"8Oqn3LpaXvgYLzF63oFHat3paon7IBjBmOX3eyd8KjirVf3empJds4uUw2Nn2m7TVvRAtJ8XzNl-8ytf"
    b"2RLtmjMx1Xkgp5VZ8S7UqJ_cKLyl76eVRtGEA1DH2HdPKu1vBPJ4bzDfnhDPYl4k5z9XSSgqAbQ9WO0U"
    b"5kiI3BYjVRZSKnZMeguAGZ47ezDj_WArGcHAB8Pa2v3HFp5Y34DMJ8r3_hD5hxCKgoNx4AHx1Q-hRDqp"
    b"Aroj-4jl7KWvlP-OJNc1BgH2wnhFmeKHotv-Iumi83JQohyceUbG6j8rDDQvJfcn0W2_ebmUH3TKr-w="
    b"="
)
VALID_UPGRADED_TEN_SEAT_LICENSE = (
    # id: "1", instance_id: "1"
    b"eyJ2ZXJzaW9uIjogMSwgImlkIjogIjEiLCAidmFsaWRfZnJvbSI6ICIyMDIxLTA4LTI5VDE5OjUyOjU3"
    b"Ljg0MjY5NiIsICJ2YWxpZF90aHJvdWdoIjogIjIwMjEtMDktMjlUMTk6NTI6NTcuODQyNjk2IiwgInBy"
    b"b2R1Y3RfY29kZSI6ICJwcmVtaXVtIiwgInNlYXRzIjogMTAsICJpc3N1ZWRfb24iOiAiMjAyMS0wOC0z"
    b"MFQxOTo1Mjo1Ny44NDI2OTYiLCAiaXNzdWVkX3RvX2VtYWlsIjogImJyYW1AYmFzZXJvdy5pbyIsICJp"
    b"c3N1ZWRfdG9fbmFtZSI6ICJCcmFtIiwgImluc3RhbmNlX2lkIjogIjEifQ==.MLZn4TG1iZbXo1kjryk"
    b"B98fFnYf8tOu8DG_I9CpkS5UGboI1-BNcq0pdtKxRgaTkRb-Q09D4J-LHKri5KA9WyQQNY8bb4antS1s"
    b"svi8Yrp6p9VQhtCunKCqUuLA8mpHFNLV6nbsTKLds5imyFSMzT-8RLejT774RUQ3-DUYd2N-awbxBwDs"
    b"Zpsupq3_7UrYIPhDcpVs_5G47p8ZT-z2fcC2cPOB2tRc6eQw7eUx95-nIxcR9IbLsHmQjYj3dxOjdsmN"
    b"SDekPuwzbQiZnDpfy7kzc93-752AHTZ-O2gd83PFZziaIJSyu7mUsxWk4rkMQalO_XG9X0AOEraT0SQQ"
    b"r0A=="
)
VALID_TWO_SEAT_LICENSE = (
    # id: "2", instance_id: "1"
    b"eyJ2ZXJzaW9uIjogMSwgImlkIjogIjIiLCAidmFsaWRfZnJvbSI6ICIyMDIxLTA4LTI5VDE5OjUzOjM3"
    b"LjA5MjMwMyIsICJ2YWxpZF90aHJvdWdoIjogIjIwMjEtMDktMjlUMTk6NTM6MzcuMDkyMzAzIiwgInBy"
    b"b2R1Y3RfY29kZSI6ICJwcmVtaXVtIiwgInNlYXRzIjogMiwgImlzc3VlZF9vbiI6ICIyMDIxLTA4LTI5"
    b"VDE5OjUzOjM3LjA5MjMwMyIsICJpc3N1ZWRfdG9fZW1haWwiOiAiYnJhbUBiYXNlcm93LmlvIiwgImlz"
    b"c3VlZF90b19uYW1lIjogIkJyYW0iLCAiaW5zdGFuY2VfaWQiOiAiMSJ9.d41tB1kx69gw-9xDrRI0kER"
    b"KDUtR-P6yRM3ufKZ_XRDewVCBAniCLe9-ce7TKabnMedE2cqHjYVLlI66Dfa5oH8fGswnyC16c9ZHlOU"
    b"jQ5CpHTorZm6eyCXaP6MDdhstCNKdDrZns3qvVMAqDpmxS8wmiG9Y6gZjvBGXZWeoCraF1SVcUnFBBlf"
    b"UemfGSQUwPitVlxJ6GWN-hzi7b1GZqWJKDb2YYJ0T30VMJeNO7oi6YHMUOH33041FU79DSET2A2NNEFu"
    b"e-jnCcw5NFpH-zGzBDv1wpR3DFmJa78KwGbj0Kdzim85AUzi1xGRlIyxxTdTkVy2B-08lPaoG8Q62bw="
    b"="
)
VALID_INSTANCE_TWO_LICENSE = (
    # id: "2", instance_id: "2"
    b"eyJ2ZXJzaW9uIjogMSwgImlkIjogIjEiLCAidmFsaWRfZnJvbSI6ICIyMDIxLTA4LTI5VDE5OjUyOjU3"
    b"Ljg0MjY5NiIsICJ2YWxpZF90aHJvdWdoIjogIjIwMjEtMDktMjlUMTk6NTI6NTcuODQyNjk2IiwgInBy"
    b"b2R1Y3RfY29kZSI6ICJwcmVtaXVtIiwgInNlYXRzIjogMSwgImlzc3VlZF9vbiI6ICIyMDIxLTA4LTI5"
    b"VDE5OjUyOjU3Ljg0MjY5NiIsICJpc3N1ZWRfdG9fZW1haWwiOiAiYnJhbUBiYXNlcm93LmlvIiwgImlz"
    b"c3VlZF90b19uYW1lIjogIkJyYW0iLCAiaW5zdGFuY2VfaWQiOiAiMiJ9.i3Og4ZJwz__TxWyFc2B6lDi"
    b"ZBAIOVTZv_jXVzQQqcjG-flPAicqXFECl7MbbexVmtsMES-U7VPebOh0t4oPoDXL1LiftfjmT63wO4An"
    b"A3FMS0Ip0GIx2upkQC-MlU1kSR9Tltrr1qySuQvXORDRUaSxaRQQacwZTOIviVdcxG9vesjkFwn6LMYp"
    b"-GhmCJXB0YfMgsvPm6kj6qTWPh3ed8aLNFnekUhB-dUwA4tqPicCQHRQCRZqzo9vx-hKdeHCGZMg0htG"
    b"EB4cAeV4I29JXPC83qtwt6DSCPxudlJsli3tYsLMcxAHysVN3H_FAY8qg54MP33OKvZuwww5uFDITMQ="
    b"="
)
VALID_ENTERPRISE_FIVE_SEAT_LICENSE = (
    # id: "3f0168af-afaf-4426-896b-b388391076e7"
    # instance_id: "6d6366b8-6f32-4549-81c2-d4a0c07a334b"
    b"eyJ2ZXJzaW9uIjogMSwgImlkIjogIjNmMDE2OGFmLWFmYWYtNDQyNi04OTZiLWIzODgzOTEwNzZlNyIsI"
    b"CJ2YWxpZF9mcm9tIjogIjIwMjEtMDEtMDFUMDA6MDA6MDAiLCAidmFsaWRfdGhyb3VnaCI6ICIyMDIxLT"
    b"EyLTMxVDIzOjU5OjU5IiwgInByb2R1Y3RfY29kZSI6ICJlbnRlcnByaXNlIiwgInNlYXRzIjogNSwgIml"
    b"zc3VlZF9vbiI6ICIyMDIzLTAxLTExVDE0OjUzOjQ1LjM3Mjk1MCIsICJpc3N1ZWRfdG9fZW1haWwiOiAi"
    b"cGV0ckBleGFtcGxlLmNvbSIsICJpc3N1ZWRfdG9fbmFtZSI6ICJwZXRyQGV4YW1wbGUuY29tIiwgImluc"
    b"3RhbmNlX2lkIjogIjZkNjM2NmI4LTZmMzItNDU0OS04MWMyLWQ0YTBjMDdhMzM0YiJ9.B6os-CyNrp5wW"
    b"3gDTwjariLS6KhUBFYBwOlDlpVkTB8BPe1yjVIxw7nRH09TXovp9oTc2iJkGY5znBxuFMbCotmnIkBTnw"
    b"p6uOhBMlPQFydzUXt1GmaWpEEcTSV7hKNVykPasEBCTK3Z4CA-eTjJBKo7vGCT7qTu01I4ghgI4aBEM5J"
    b"qMe-ngEomRVnRMPAEgCNjFB44rVAB3zcJfPuBoukRB2FjOw1ddEkA3DjwcHlhkj1NcETlyUpFbFtCjhtL"
    b"oowm_5CZm8Ba6eL-YgI2vKTWfMsVZ9GkJxcaiK3d-AB_ipjub-VVyNXPiVWab7108w3EXmoZIvmhCc67g"
    b"bL3jA=="
)
VALID_PREMIUM_TEN_SEAT_TEN_APP_USER_LICENSE = (
    # id: "c26e4ef2-0492-4571-ad0d-49ca808c14b5"
    # instance_id: "1"
    b"eyJ2ZXJzaW9uIjogMSwgImlkIjogImMyNmU0ZWYyLTA0OTItNDU3MS1hZDBkLTQ5Y2E4MDhjMTRiNSIsI"
    b"CJ2YWxpZF9mcm9tIjogIjIwMjUtMDItMDFUMDA6MDA6MDAiLCAidmFsaWRfdGhyb3VnaCI6ICIyMDI4LT"
    b"AxLTAxVDIzOjU5OjU5IiwgInByb2R1Y3RfY29kZSI6ICJwcmVtaXVtIiwgInNlYXRzIjogMTAsICJhcHB"
    b"saWNhdGlvbl91c2VycyI6IDEwLCAiaXNzdWVkX29uIjogIjIwMjUtMDItMTFUMTM6MzY6MjEuMDc1ODcz"
    b"IiwgImlzc3VlZF90b19lbWFpbCI6ICJwZXRlckBiYXNlcm93LmlvIiwgImlzc3VlZF90b19uYW1lIjogI"
    b"lBldGVyIiwgImluc3RhbmNlX2lkIjogIjEifQ==.tEholymqZF9aoYUAPDvufzCLylDk92MVpb6J7XJEs"
    b"k0zdgMdKwlrvCqNBpqtfDWJYJWKVxX4xk4NjTPBjdPbSRZM--kSL1uBa6djpLUU0XoXaOg74P39PW7gcQ"
    b"qrsWbZRdDWn6fFePWQ4U9w83t5OvxflZE2Qd8tvWYAVbgKRZXbpkzKoJgMrGoC2QVBIqy6KA3FZxw5EVT"
    b"KfMTkE34y8SsmTsvlDmLlt2fpkrFwM2Vpi4mE7GiY4nf5f4_8UHckpG8tqA-OK6KV4kPL_aTTLwdcZDL-"
    b"aULpNydqXUfGMMgKzjq1L1cULsoZQc9ueFZBh8KmA2PEjw4i1o70-xePIA=="
)
VALID_PREMIUM_5_SEAT_15_APP_USER_LICENSE = (
    b"eyJ2ZXJzaW9uIjogMSwgImlkIjogImY4YjRlOTk1LTJhMmEtNDg0NS04ZWI1LWM2MjBiYzA5YTdiMiIsI"
    b"CJ2YWxpZF9mcm9tIjogIjIwMjUtMDItMDFUMDA6MDA6MDAiLCAidmFsaWRfdGhyb3VnaCI6ICIyMDI2LT"
    b"AxLTAxVDIzOjU5OjU5IiwgInByb2R1Y3RfY29kZSI6ICJwcmVtaXVtIiwgInNlYXRzIjogNSwgImFwcGx"
    b"pY2F0aW9uX3VzZXJzIjogMTUsICJpc3N1ZWRfb24iOiAiMjAyNS0wMi0xN1QxMTo0NToyNC44NjM3NjQi"
    b"LCAiaXNzdWVkX3RvX2VtYWlsIjogInBldGVyQGJhc2Vyb3cuaW8iLCAiaXNzdWVkX3RvX25hbWUiOiAiU"
    b"GV0ZXIiLCAiaW5zdGFuY2VfaWQiOiAiMSJ9.GsYLPV63FG5FAncOp6dyLysDqVSMR37C1zwTT-otZgGuu"
    b"TpYg4aa9x-2ODonL9IAUmosyy6FZ1LcI4i8YdDyQ_rt-X_KhwR2S7Eotl6ZEepOYTbC7qKuG30szAKM6d"
    b"4eL0unPB48pLJhSS_j745WgMn-4vUMmm6FTWaIPJaWFzwUjOp5zLgNpvvgkayzQ608XdYVjilVBcTlszj"
    b"hxi00g0la2nMdCqDytZdJCn7XwAMA8itvSjYrWL1gMqTtPL6U92bJz97n8wQRBFW8kNKb2JTPfcbwozeg"
    b"Vd44sPwBqWaA0wwpKyNs-Sa43FHcbQKIGG8A68hKQy2MG3EWHgLWTA=="
)
VALID_ENTERPRISE_FIFTEEN_SEAT_FIFTEEN_APP_USER_LICENSE = (
    # id: "06b9bec3-d5d9-4286-be5a-c25b94188303"
    # instance_id: "1"
    b"eyJ2ZXJzaW9uIjogMSwgImlkIjogIjA2YjliZWMzLWQ1ZDktNDI4Ni1iZTVhLWMyNWI5NDE4ODMwMyIsI"
    b"CJ2YWxpZF9mcm9tIjogIjIwMjUtMDItMDFUMDA6MDA6MDAiLCAidmFsaWRfdGhyb3VnaCI6ICIyMDI4LT"
    b"AxLTAxVDIzOjU5OjU5IiwgInByb2R1Y3RfY29kZSI6ICJlbnRlcnByaXNlIiwgInNlYXRzIjogMTUsICJ"
    b"hcHBsaWNhdGlvbl91c2VycyI6IDE1LCAiaXNzdWVkX29uIjogIjIwMjUtMDItMTFUMTM6MzU6MjYuODYy"
    b"NTg3IiwgImlzc3VlZF90b19lbWFpbCI6ICJwZXRlckBiYXNlcm93LmlvIiwgImlzc3VlZF90b19uYW1lI"
    b"jogIlBldGVyIiwgImluc3RhbmNlX2lkIjogIjEifQ==.u1ws8JSZHta15GVqiUdQRb592aeIuAUxSNMDm"
    b"_WAY1rSFzeY74MLhl7aQ3ZB5JalUwuT8Bi1PqCBqiSSVJGdF5pL4u25Gwn10mNDvfXmRh34DvV7ZIYdpV"
    b"C_WiPOkeojoXtawuNmIzePON1pAv6TfG9Qq_57vSshht49TiG2PTYGdeeZa9sbrP589dhkIk0UY6Z6aCZ"
    b"voGAXz0rbrsS6lQUFqkYdBgA4LpgsrWWjLRxKdmy64CYj1k37ERtU8w-uauhYW3IUHDmDiZQYjNrL7g7q"
    b"Elk5YJBqjseMM_J4VkgULax1TDyG-q114UKCeCrCFA4pqsbxvGJ41-Le_-JOEg=="
)
INVALID_SIGNATURE_LICENSE = (
    b"eyJ2ZXJzaW9uIjogMSwgImlkIjogMSwgInZhbGlkX2Zyb20iOiAiMjAyMS0wOC0yOVQxOTo1NDoxMi4w"
    b"NjY4NDYiLCAidmFsaWRfdGhyb3VnaCI6ICIyMDIxLTA5LTI5VDE5OjU0OjEyLjA2Njg0NiIsICJwcm9k"
    b"dWN0X2NvZGUiOiAicHJlbWl1bSIsICJzZWF0cyI6IDEsICJ0b19lbWFpbCI6ICJicmFtQGJhc2Vyb3cu"
    b"aW8iLCAidG9fbmFtZSI6ICJCcmFtIn0=.hYaWGO0M6s1pA9bhcBlk1fE1QMrhlDGNiBIBG_2O2AMGFPj"
    b"gnsHdwfUIe_eo6dyAyvsToxBrpxr6N1vRqPdA61cKjTlhUdFqvj7NTeydS4Z9TlfP-vFslQk9CO_ok7Z"
    b"ws8AHTQ2pKfsdzqcWNZnWKZeQGEtO73MIoFJbHr07mtWA1ZZgJNBTBpp-7BNtvj2bQyUeXyRKD5LVj8G"
    b"ESDcapZCNt5ufesbYvpfs1c6p6UP4z3gszOYrzMApMqWHty7j10SDjcLIEsUTd02r_Pbip-KxmGfecXg"
    b"B0HF7HJZwkY9ZdlZ7ODGtV0e455dQwh5sSHa3RRd71AXVou-cuOS87g=="
)
INVALID_PAYLOAD_LICENSE = (
    b"e30=.gtDuoJAHn-LTPX1ReoGo8cm3DsXq0mf9MwpIccwCQXucpnh-r6yeJzRGbx5F80OGKXZJ1XcxLRr"
    b"8-IssyxlGVcrhHt6iYXmNoPXUrxN1slOzMO4_tutvEHSuOntW5gctm9SFfcRrdbejYue_47brp779bP2"
    b"pzwejOdQbSLUeNQ4bHIKQJYZ4cCooW8yICz6a8m4NFRDu_gr0Y1ud1Eo3h2E_BL2upNg14v8BRZJCHpj"
    b"CC5Eg4ErKqm88iFStIEpub-vem9rEwKR2kIvdJ6DaD7AJTG507GEtbI9lNCkm2aPJSf142Rf8_NrTVh3"
    b"QBqZnCo-XrquQe1h4r3fvjAf5tQ=="
)
INVALID_VERSION_LICENSE = (
    b"eyJ2ZXJzaW9uIjogOTk5OX0=.rzAyL6qBkz_Eb3GYaSOXy9CJ2HJg4uAxtrbinh4aDYy7Eq4e4RpfaPm"
    b"4dZLocIRxSmx_wUYSI0CMqmkwABHgzxRVmzVAmXf5MxX7vAGjjEnQX_dQOl8kY15gXhEQZv5pjSPVcZW"
    b"CLll95OFoBUJhtOQqNC6JLA1LZdiSPG6zFhvi5V27sRGBz3E8jhFLWY-Y2WIq5_9q2d_hVFM0KHwRcxb"
    b"CVof8RBUq1DgMcDKEGE7WRHYDVP1QugBjf4GZlvIE4ZVr3tKr0aKPX8nuNVhbQeudCW8tnturmxevpRN"
    b"vLS5ETSQzJoP46cGuw0HUV20P4SnvQP_NRd5zifgllJqsUw=="
)
INVALID_PREMIUM_FIVE_SEAT_10_APP_USER_EXPIRED_LICENSE = (
    b"eyJ2ZXJzaW9uIjogMSwgImlkIjogIjkzZDExODYwLTU1Y2UtNDJhYy05NGI5LTY0YTlhMTBiNzI3MiIsI"
    b"CJ2YWxpZF9mcm9tIjogIjIwMjUtMDItMDFUMDA6MDA6MDAiLCAidmFsaWRfdGhyb3VnaCI6ICIyMDI1LT"
    b"AyLTA4VDIzOjU5OjU5IiwgInByb2R1Y3RfY29kZSI6ICJwcmVtaXVtIiwgInNlYXRzIjogNSwgImFwcGx"
    b"pY2F0aW9uX3VzZXJzIjogMTAsICJpc3N1ZWRfb24iOiAiMjAyNS0wMi0xOFQxMToxMDowNS40NjE3NzAi"
    b"LCAiaXNzdWVkX3RvX2VtYWlsIjogInBldGVyQGJhc2Vyb3cuaW8iLCAiaXNzdWVkX3RvX25hbWUiOiAiU"
    b"GV0ZXIiLCAiaW5zdGFuY2VfaWQiOiAiMSJ9.DJXyKA1MEMcR7hLFiITLteBQbgZhLpOVqLT1GoWqiC60B"
    b"WiEz223qTnYE06ibqMF_YF__Cr1ejS7brplUa1_56G0MDtTobVzH5-IJIiVt1KXGkUoYZdCuD6ouk9maH"
    b"2ycOWEqZZsWROaLJ_ipzyxbYeiVrBuYEv5P5IhsmeEbAH9Gj5e4vjkwHmZjZGlW-4Ejo8NXC6uhdcxx7b"
    b"t89MaAKEk-cYmtKL0eJEUrKvU2drHuo0ft6QusXHyzROPD82h1pgBNQNDSkHwmY9hxaHdbCjsojPVLARU"
    b"tsAx2YIDwpQ5QDyPA1s6OqG4e72l1sUUE4fxjHF7-FKEHQwAsvOZzg=="
)
NOT_JSON_PAYLOAD_LICENSE = (
    b"dGVzdA==.I37aSmuKN0WSrw6IDTg2xBOlQ3UOE5cjaWfc4MF5pgIadMUjkOh0D32R7RqRhmsxhdsqK6a"
    b"bU8u8cT6ZG0PxjsRnFjrkbhdcFR1Yw9fHQ7plHShnpsj0NT8fMuDaVfCibKxyi-Z8nVmwHEIlyRkLfKV"
    b"NMTR7q2bzdM9-LZ-jJsgp4qqtSE8ct8YwwdwUS8clKzb-wVyCDeGD2kBRyxNRU_hhiwN_aDv6zEEqd6u"
    b"1lkIxotWs8hHJ3kT9EB9LY9Nb5qlm9Qt4bJY9OB4Bc8eEpXgEXGMUik11sTo5E3thoV6HJTUQWLwozbo"
    b"fXwhO9qsjxisGZPEFinezHN124jSWxQ=="
)


def has_active_premium_license_features(user):
    return LicenseHandler.user_has_feature_instance_wide(PREMIUM, user)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_has_active_premium_license(data_fixture):
    user_in_license = data_fixture.create_user()
    second_user_in_license = data_fixture.create_user()
    user_not_in_license = data_fixture.create_user()
    license = License.objects.create(license=VALID_TWO_SEAT_LICENSE.decode())
    License.objects.create(license=VALID_ONE_SEAT_LICENSE.decode())
    LicenseUser.objects.create(license=license, user=user_in_license)
    license_user_2 = LicenseUser.objects.create(
        license=license, user=second_user_in_license
    )

    with freeze_time("2021-08-01 12:00"), local_cache.context():
        assert not has_active_premium_license_features(user_in_license)
        assert not has_active_premium_license_features(second_user_in_license)
        assert not has_active_premium_license_features(user_not_in_license)

    with freeze_time("2021-09-01 12:00"), local_cache.context():
        assert has_active_premium_license_features(user_in_license)
        assert has_active_premium_license_features(second_user_in_license)
        assert not has_active_premium_license_features(user_not_in_license)

    with freeze_time("2021-10-01 12:00"), local_cache.context():
        assert not has_active_premium_license_features(user_in_license)
        assert not has_active_premium_license_features(second_user_in_license)
        assert not has_active_premium_license_features(user_not_in_license)

    license_user_2.delete()
    with freeze_time("2021-09-01 12:00"), local_cache.context():
        assert has_active_premium_license_features(user_in_license)
        assert not has_active_premium_license_features(second_user_in_license)
        assert not has_active_premium_license_features(user_not_in_license)

        LicenseHandler.raise_if_user_doesnt_have_feature_instance_wide(
            PREMIUM, user_in_license
        )

        with pytest.raises(FeaturesNotAvailableError):
            LicenseHandler.raise_if_user_doesnt_have_feature_instance_wide(
                PREMIUM, second_user_in_license
            )

        with pytest.raises(FeaturesNotAvailableError):
            LicenseHandler.raise_if_user_doesnt_have_feature_instance_wide(
                PREMIUM, user_not_in_license
            )

    # When the license can't be decoded, it should also return false.
    invalid_user = data_fixture.create_user()
    invalid_license = License.objects.create(license="invalid")
    LicenseUser.objects.create(license=invalid_license, user=invalid_user)
    assert not has_active_premium_license_features(invalid_user)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_check_active_premium_license_for_workspace_with_valid_license(data_fixture):
    user_in_license = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user_in_license)
    license = License.objects.create(license=VALID_TWO_SEAT_LICENSE.decode())
    LicenseUser.objects.create(license=license, user=user_in_license)

    with freeze_time("2021-08-01 12:00"):
        with pytest.raises(FeaturesNotAvailableError):
            LicenseHandler.raise_if_user_doesnt_have_feature(
                PREMIUM, user_in_license, workspace
            )

    with freeze_time("2021-09-01 12:00"):
        LicenseHandler.raise_if_user_doesnt_have_feature(
            PREMIUM, user_in_license, workspace
        )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_check_active_premium_license_for_workspace_with_per_workspace_licenses(
    data_fixture, alternative_per_workspace_license_service
):
    user_in_license = data_fixture.create_user()
    workspace_1 = data_fixture.create_workspace(user=user_in_license)
    workspace_2 = data_fixture.create_workspace(user=user_in_license)
    workspace_3 = data_fixture.create_workspace(user=user_in_license)
    workspace_4 = data_fixture.create_workspace(user=user_in_license)

    alternative_per_workspace_license_service.restrict_user_premium_to(
        user_in_license, [workspace_1.id, workspace_2.id]
    )

    LicenseHandler.raise_if_user_doesnt_have_feature(
        PREMIUM, user_in_license, workspace_1
    )
    LicenseHandler.raise_if_user_doesnt_have_feature(
        PREMIUM, user_in_license, workspace_2
    )

    with pytest.raises(FeaturesNotAvailableError):
        LicenseHandler.raise_if_user_doesnt_have_feature(
            PREMIUM, user_in_license, workspace_3
        )

    with pytest.raises(FeaturesNotAvailableError):
        LicenseHandler.raise_if_user_doesnt_have_feature(
            PREMIUM, user_in_license, workspace_4
        )


@override_settings(DEBUG=True)
def test_get_public_key_debug():
    public_key = LicenseHandler.get_public_key()
    signature = base64.b64decode(
        b"UnRzVNbgO8XxAHEjn6uzGrjdVjwf5rU2BcOe+G2nKHhF50m8nf/DAmmk6rsCFolrCXke2tJFnER"
        b"0aeoPKwjZItnYJhkX0xt1PwkpImBoSZYQfdGycVuLwRv28yQaWP1tGonNIqpUuAiyuTrTEOWPid"
        b"vbaYtAXu/I9aRwBSpjD3cM8mvyb4BE/lsC6RC1qYj6V2vUmoWum8sCQLHcToAs75CjV8NVVH97X"
        b"TUnUellH3s+UpwHL9Rauq8rnPdAWLf6wujcqeBtdtsjp4HakuTsNYK+AcceSGeGSrlVqD0OoQei"
        b"Cc2d0/5SkO3DyndZ/X73eX2psYpyd0p1ZDkCSbKJpA=="
    )

    # We do not expect the `InvalidSignature` exception.
    assert (
        public_key.verify(
            signature,
            b"test",
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256(),
        )
        is None
    )


@override_settings(DEBUG=False)
def test_get_public_key_production():
    public_key = LicenseHandler.get_public_key()
    signature = base64.b64decode(
        b"UnRzVNbgO8XxAHEjn6uzGrjdVjwf5rU2BcOe+G2nKHhF50m8nf/DAmmk6rsCFolrCXke2tJFnER"
        b"0aeoPKwjZItnYJhkX0xt1PwkpImBoSZYQfdGycVuLwRv28yQaWP1tGonNIqpUuAiyuTrTEOWPid"
        b"vbaYtAXu/I9aRwBSpjD3cM8mvyb4BE/lsC6RC1qYj6V2vUmoWum8sCQLHcToAs75CjV8NVVH97X"
        b"TUnUellH3s+UpwHL9Rauq8rnPdAWLf6wujcqeBtdtsjp4HakuTsNYK+AcceSGeGSrlVqD0OoQei"
        b"Cc2d0/5SkO3DyndZ/X73eX2psYpyd0p1ZDkCSbKJpA=="
    )

    # We expect the `InvalidSignature` exception because the signature has been
    # signed with the wrong private key. This way, we know the debug key is not used
    # in production.
    with pytest.raises(InvalidSignature):
        public_key.verify(
            signature,
            b"test",
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256(),
        )


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_fetch_license_status_with_authority_unavailable(data_fixture):
    data_fixture.update_settings(instance_id="1")

    with pytest.raises(LicenseAuthorityUnavailable):
        LicenseHandler.fetch_license_status_with_authority(["test"])

    responses.add(
        responses.POST,
        "http://baserow-saas-backend:8000/api/saas/licenses/check/",
        json={"error": "error"},
        status=400,
    )

    with pytest.raises(LicenseAuthorityUnavailable):
        LicenseHandler.fetch_license_status_with_authority(["test"])

    responses.add(
        responses.POST,
        "http://baserow-saas-backend:8000/api/saas/licenses/check/",
        body="not_json",
        status=200,
    )

    with pytest.raises(LicenseAuthorityUnavailable):
        LicenseHandler.fetch_license_status_with_authority(["test"])


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_fetch_license_status_with_authority_invalid_response(data_fixture):
    data_fixture.update_settings(instance_id="1")

    responses.add(
        responses.POST,
        "http://baserow-saas-backend:8000/api/saas/licenses/check/",
        body="not_json",
        status=200,
    )

    with pytest.raises(LicenseAuthorityUnavailable):
        LicenseHandler.fetch_license_status_with_authority(["test"])


@pytest.mark.django_db
@override_settings(DEBUG=False)
@responses.activate
def test_fetch_license_status_in_production_mode(data_fixture):
    data_fixture.update_settings(instance_id="1")

    responses.add(
        responses.POST,
        "https://api.baserow.io/api/saas/licenses/check/",
        json={"success": True},
        status=200,
    )

    response = LicenseHandler.fetch_license_status_with_authority(["test"])
    assert response["success"] is True


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_fetch_license_status_with_authority(data_fixture):
    data_fixture.update_settings(instance_id="1")

    responses.add(
        responses.POST,
        "http://baserow-saas-backend:8000/api/saas/licenses/check/",
        json={"test": {"type": "ok", "detail": ""}},
        status=200,
    )

    response = LicenseHandler.fetch_license_status_with_authority(["test"])
    assert len(response) == 1
    assert response["test"]["type"] == "ok"


@pytest.mark.django_db
@override_settings(DEBUG=True)
# Activate the responses because we want to check with the authority to fail.
@responses.activate
def test_check_licenses_with_authority_check(premium_data_fixture):
    invalid_license = premium_data_fixture.create_premium_license(license="invalid")
    does_not_exist_license = premium_data_fixture.create_premium_license(
        license="does_not_exist"
    )
    instance_id_mismatch_license = premium_data_fixture.create_premium_license(
        license="instance_id_mismatch"
    )
    updated_license = premium_data_fixture.create_premium_license(license="update")
    valid_license_without_builder = premium_data_fixture.create_premium_license(
        license=VALID_TWO_SEAT_LICENSE.decode()
    )
    valid_license_with_builder = premium_data_fixture.create_premium_license(
        license=VALID_PREMIUM_TEN_SEAT_TEN_APP_USER_LICENSE.decode()
    )

    with freeze_time("2021-07-01 12:00"):
        responses.add(
            responses.POST,
            "http://baserow-saas-backend:8000/api/saas/licenses/check/",
            json={
                "invalid": {"type": "invalid", "detail": ""},
                "does_not_exist": {"type": "does_not_exist", "detail": ""},
                "instance_id_mismatch": {
                    "type": "instance_id_mismatch",
                    "detail": "",
                },
                "update": {
                    "type": "update",
                    "detail": "",
                    "new_license_payload": VALID_ONE_SEAT_LICENSE.decode(),
                },
                VALID_TWO_SEAT_LICENSE.decode(): {"type": "ok", "detail": ""},
                VALID_PREMIUM_TEN_SEAT_TEN_APP_USER_LICENSE.decode(): {
                    "type": "ok",
                    "detail": "",
                },
            },
            status=200,
        )

        LicenseHandler.check_licenses(
            [
                invalid_license,
                does_not_exist_license,
                instance_id_mismatch_license,
                updated_license,
                valid_license_without_builder,
                valid_license_with_builder,
            ]
        )

        all_licenses = License.objects.all().order_by("id")
        assert len(all_licenses) == 3
        assert all_licenses[0].id == updated_license.id
        assert all_licenses[0].license == VALID_ONE_SEAT_LICENSE.decode()
        assert all_licenses[0].license_id == "1"
        assert all_licenses[0].last_check.year == 2021
        assert all_licenses[1].id == valid_license_without_builder.id
        assert all_licenses[1].last_check.year == 2021
        assert all_licenses[2].id == valid_license_with_builder.id
        assert all_licenses[2].last_check.year == 2021


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_check_licenses_update_instance_wide(premium_data_fixture):
    updated_license = premium_data_fixture.create_premium_license(license="update")

    with freeze_time("2021-07-01 12:00"):
        responses.add(
            responses.POST,
            "http://baserow-saas-backend:8000/api/saas/licenses/check/",
            json={
                "update": {
                    "type": "update",
                    "detail": "",
                    "new_license_payload": VALID_ENTERPRISE_FIVE_SEAT_LICENSE.decode(),
                },
                VALID_TWO_SEAT_LICENSE.decode(): {"type": "ok", "detail": ""},
            },
            status=200,
        )

        LicenseHandler.check_licenses(
            [
                updated_license,
            ]
        )

        all_licenses = License.objects.all().order_by("id")
        assert all_licenses[0].id == updated_license.id
        assert all_licenses[0].license == VALID_ENTERPRISE_FIVE_SEAT_LICENSE.decode()
        assert all_licenses[0].cached_untrusted_instance_wide is True


@pytest.mark.django_db
@override_settings(DEBUG=True)
# Activate the responses because we want to check with the authority to fail.
@responses.activate
def test_check_licenses_without_authority_check(premium_data_fixture):
    with freeze_time("2021-07-01 12:00"):
        license_object = premium_data_fixture.create_premium_license(
            license=VALID_TWO_SEAT_LICENSE.decode()
        )
        premium_data_fixture.create_premium_license_user(license=license_object)
        premium_data_fixture.create_premium_license_user(license=license_object)
        premium_data_fixture.create_premium_license_user(license=license_object)
        premium_data_fixture.create_premium_license_user(license=license_object)

        # This license is expected to be delete because the payload is invalid.
        license_object_2 = premium_data_fixture.create_premium_license(
            license="invalid_license"
        )

        assert License.objects.all().count() == 2
        assert license_object.users.all().count() == 4
        LicenseHandler.check_licenses([license_object, license_object_2])
        assert License.objects.all().count() == 1
        assert license_object.users.all().count() == 2
        assert license_object.last_check.year == 2021


@override_settings(DEBUG=True)
def test_decode_license_with_valid_license():
    assert LicenseHandler.decode_license(VALID_ONE_SEAT_LICENSE) == {
        "version": 1,
        "id": "1",
        "valid_from": "2021-08-29T19:52:57.842696",
        "valid_through": "2021-09-29T19:52:57.842696",
        "product_code": "premium",
        "seats": 1,
        "issued_on": "2021-08-29T19:52:57.842696",
        "issued_to_email": "bram@baserow.io",
        "issued_to_name": "Bram",
        "instance_id": "1",
    }
    assert LicenseHandler.decode_license(VALID_UPGRADED_TEN_SEAT_LICENSE) == {
        "version": 1,
        "id": "1",
        "valid_from": "2021-08-29T19:52:57.842696",
        "valid_through": "2021-09-29T19:52:57.842696",
        "product_code": "premium",
        "seats": 10,
        "issued_on": "2021-08-30T19:52:57.842696",
        "issued_to_email": "bram@baserow.io",
        "issued_to_name": "Bram",
        "instance_id": "1",
    }
    assert LicenseHandler.decode_license(VALID_TWO_SEAT_LICENSE) == {
        "version": 1,
        "id": "2",
        "valid_from": "2021-08-29T19:53:37.092303",
        "valid_through": "2021-09-29T19:53:37.092303",
        "product_code": "premium",
        "seats": 2,
        "issued_on": "2021-08-29T19:53:37.092303",
        "issued_to_email": "bram@baserow.io",
        "issued_to_name": "Bram",
        "instance_id": "1",
    }
    assert LicenseHandler.decode_license(VALID_INSTANCE_TWO_LICENSE) == {
        "version": 1,
        "id": "1",
        "valid_from": "2021-08-29T19:52:57.842696",
        "valid_through": "2021-09-29T19:52:57.842696",
        "product_code": "premium",
        "seats": 1,
        "issued_on": "2021-08-29T19:52:57.842696",
        "issued_to_email": "bram@baserow.io",
        "issued_to_name": "Bram",
        "instance_id": "2",
    }
    assert LicenseHandler.decode_license(VALID_ENTERPRISE_FIVE_SEAT_LICENSE) == {
        "version": 1,
        "id": "3f0168af-afaf-4426-896b-b388391076e7",
        "valid_from": "2021-01-01T00:00:00",
        "valid_through": "2021-12-31T23:59:59",
        "product_code": "enterprise",
        "seats": 5,
        "issued_on": "2023-01-11T14:53:45.372950",
        "issued_to_email": "petr@example.com",
        "issued_to_name": "petr@example.com",
        "instance_id": "6d6366b8-6f32-4549-81c2-d4a0c07a334b",
    }
    assert LicenseHandler.decode_license(
        VALID_ENTERPRISE_FIFTEEN_SEAT_FIFTEEN_APP_USER_LICENSE
    ) == {
        "version": 1,
        "id": "06b9bec3-d5d9-4286-be5a-c25b94188303",
        "valid_from": "2025-02-01T00:00:00",
        "valid_through": "2028-01-01T23:59:59",
        "product_code": "enterprise",
        "seats": 15,
        "application_users": 15,
        "issued_on": "2025-02-11T13:35:26.862587",
        "issued_to_email": "peter@baserow.io",
        "issued_to_name": "Peter",
        "instance_id": "1",
    }
    assert LicenseHandler.decode_license(
        VALID_PREMIUM_TEN_SEAT_TEN_APP_USER_LICENSE
    ) == {
        "version": 1,
        "id": "c26e4ef2-0492-4571-ad0d-49ca808c14b5",
        "valid_from": "2025-02-01T00:00:00",
        "valid_through": "2028-01-01T23:59:59",
        "product_code": "premium",
        "seats": 10,
        "application_users": 10,
        "issued_on": "2025-02-11T13:36:21.075873",
        "issued_to_email": "peter@baserow.io",
        "issued_to_name": "Peter",
        "instance_id": "1",
    }


@override_settings(DEBUG=True)
def test_invalid_signature_decode_license():
    with pytest.raises(InvalidLicenseError):
        LicenseHandler.decode_license(INVALID_SIGNATURE_LICENSE)

    with pytest.raises(InvalidLicenseError):
        LicenseHandler.decode_license(INVALID_PAYLOAD_LICENSE)

    with pytest.raises(InvalidLicenseError):
        LicenseHandler.decode_license(b"test")

    with pytest.raises(InvalidLicenseError):
        LicenseHandler.decode_license(b"test.test")

    with pytest.raises(InvalidLicenseError):
        LicenseHandler.decode_license(b"test.test==")

    with pytest.raises(InvalidLicenseError):
        LicenseHandler.decode_license(b"eyJ2ZXJzaW9uIjog.rzAyL6qBkz_Eb==")

    with pytest.raises(InvalidLicenseError):
        LicenseHandler.decode_license(NOT_JSON_PAYLOAD_LICENSE)


@override_settings(DEBUG=True)
def test_unsupported_version_decode_license():
    with pytest.raises(UnsupportedLicenseError):
        LicenseHandler.decode_license(INVALID_VERSION_LICENSE)


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_register_license_with_authority_check_ok(data_fixture):
    data_fixture.update_settings(instance_id="1")
    admin_user = data_fixture.create_user(is_staff=True)

    with freeze_time("2021-07-01 12:00"):
        responses.add(
            responses.POST,
            "http://baserow-saas-backend:8000/api/saas/licenses/check/",
            json={VALID_ONE_SEAT_LICENSE.decode(): {"type": "ok", "detail": ""}},
            status=200,
        )

        license_1 = LicenseHandler.register_license(admin_user, VALID_ONE_SEAT_LICENSE)
        assert license_1.license == VALID_ONE_SEAT_LICENSE.decode()


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_register_license_with_authority_check_updated(data_fixture):
    data_fixture.update_settings(instance_id="1")
    admin_user = data_fixture.create_user(is_staff=True)

    with freeze_time("2021-07-01 12:00"):
        responses.add(
            responses.POST,
            "http://baserow-saas-backend:8000/api/saas/licenses/check/",
            json={
                VALID_ONE_SEAT_LICENSE.decode(): {
                    "type": "update",
                    "detail": "",
                    "new_license_payload": VALID_UPGRADED_TEN_SEAT_LICENSE.decode(),
                }
            },
            status=200,
        )

        license_1 = LicenseHandler.register_license(admin_user, VALID_ONE_SEAT_LICENSE)
        assert license_1.license == VALID_UPGRADED_TEN_SEAT_LICENSE.decode()
        assert license_1.license_id == "1"


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_register_license_with_authority_check_does_not_exist(data_fixture):
    data_fixture.update_settings(instance_id="1")
    admin_user = data_fixture.create_user(is_staff=True)

    with freeze_time("2021-07-01 12:00"):
        responses.add(
            responses.POST,
            "http://baserow-saas-backend:8000/api/saas/licenses/check/",
            json={
                VALID_ONE_SEAT_LICENSE.decode(): {
                    "type": "does_not_exist",
                    "detail": "",
                }
            },
            status=200,
        )

        with pytest.raises(InvalidLicenseError):
            LicenseHandler.register_license(admin_user, VALID_ONE_SEAT_LICENSE)


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_register_license_with_authority_check_instance_id_mismatch(data_fixture):
    data_fixture.update_settings(instance_id="1")
    admin_user = data_fixture.create_user(is_staff=True)

    with freeze_time("2021-07-01 12:00"):
        responses.add(
            responses.POST,
            "http://baserow-saas-backend:8000/api/saas/licenses/check/",
            json={
                VALID_ONE_SEAT_LICENSE.decode(): {
                    "type": "instance_id_mismatch",
                    "detail": "",
                }
            },
            status=200,
        )

        with pytest.raises(LicenseInstanceIdMismatchError):
            LicenseHandler.register_license(admin_user, VALID_ONE_SEAT_LICENSE)


@pytest.mark.django_db
@override_settings(DEBUG=True)
@responses.activate
def test_register_license_with_authority_check_invalid(data_fixture):
    data_fixture.update_settings(instance_id="1")
    admin_user = data_fixture.create_user(is_staff=True)

    with freeze_time("2021-07-01 12:00"):
        responses.add(
            responses.POST,
            "http://baserow-saas-backend:8000/api/saas/licenses/check/",
            json={
                VALID_ONE_SEAT_LICENSE.decode(): {
                    "type": "invalid",
                    "detail": "",
                }
            },
            status=200,
        )

        with pytest.raises(InvalidLicenseError):
            LicenseHandler.register_license(admin_user, VALID_ONE_SEAT_LICENSE)


@pytest.mark.django_db
@override_settings(DEBUG=True)
# We need to activate the responses here, so that the license authority check will
# fail and therefore be ignored. There is another test, that tests the authority
# responses.
@responses.activate
def test_register_license(data_fixture):
    data_fixture.update_settings(instance_id="1")
    normal_user = data_fixture.create_user()
    admin_user = data_fixture.create_user(is_staff=True)

    with pytest.raises(IsNotAdminError):
        LicenseHandler.register_license(normal_user, VALID_ONE_SEAT_LICENSE)

    with freeze_time("2021-10-01 12:00"):
        with pytest.raises(LicenseHasExpiredError):
            LicenseHandler.register_license(admin_user, VALID_ONE_SEAT_LICENSE)

    with freeze_time("2021-07-01 12:00"):
        license_1 = LicenseHandler.register_license(admin_user, VALID_ONE_SEAT_LICENSE)
        assert license_1.license == VALID_ONE_SEAT_LICENSE.decode()

        # Check if the license has actually been created.
        all_licenses = License.objects.all()
        assert len(all_licenses) == 1
        assert all_licenses[0].id == license_1.id

    with freeze_time("2021-09-01 12:00"):
        with pytest.raises(LicenseInstanceIdMismatchError):
            LicenseHandler.register_license(admin_user, VALID_INSTANCE_TWO_LICENSE)

        with pytest.raises(LicenseAlreadyExistsError):
            LicenseHandler.register_license(admin_user, VALID_ONE_SEAT_LICENSE)

        license_2 = LicenseHandler.register_license(
            admin_user, VALID_TWO_SEAT_LICENSE.decode()
        )
        assert license_2.license == VALID_TWO_SEAT_LICENSE.decode()


@pytest.mark.django_db
@override_settings(DEBUG=True)
# We need to activate the responses here, so that the license authority check will
# fail and therefore be ignored. There is another test, that tests the authority
# responses.
@responses.activate
def test_upgrade_license_by_register(data_fixture):
    data_fixture.update_settings(instance_id="1")
    admin_user = data_fixture.create_user(is_staff=True)

    with freeze_time("2021-07-01 12:00"):
        first_license_1 = LicenseHandler.register_license(
            admin_user, VALID_ONE_SEAT_LICENSE
        )
        second_license_1 = LicenseHandler.register_license(
            admin_user, VALID_UPGRADED_TEN_SEAT_LICENSE
        )

        assert first_license_1.id == second_license_1.id
        assert License.objects.all().count() == 1
        assert second_license_1.license_id == "1"
        assert second_license_1.seats == 10


@pytest.mark.django_db
@override_settings(DEBUG=True)
# We need to activate the responses here, so that the license authority check will
# fail and therefore be ignored. There is another test, that tests the authority
# responses.
@responses.activate
def test_register_an_older_license(data_fixture):
    data_fixture.update_settings(instance_id="1")
    admin_user = data_fixture.create_user(is_staff=True)

    with freeze_time("2021-07-01 12:00"):
        LicenseHandler.register_license(admin_user, VALID_UPGRADED_TEN_SEAT_LICENSE)

        # The same license already exists.
        with pytest.raises(LicenseAlreadyExistsError):
            LicenseHandler.register_license(admin_user, VALID_UPGRADED_TEN_SEAT_LICENSE)

        # An older license already exists.
        with pytest.raises(LicenseAlreadyExistsError):
            LicenseHandler.register_license(admin_user, VALID_ONE_SEAT_LICENSE)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_remove_license(data_fixture):
    user_1 = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    admin_1 = data_fixture.create_user(is_staff=True)

    license_object = License.objects.create(license=VALID_TWO_SEAT_LICENSE.decode())
    LicenseUser.objects.create(license=license_object, user=user_1)
    license_object_2 = License.objects.create(license=VALID_TWO_SEAT_LICENSE.decode())
    LicenseUser.objects.create(license=license_object_2, user=user_1)
    LicenseUser.objects.create(license=license_object_2, user=user_2)

    with pytest.raises(IsNotAdminError):
        LicenseHandler.remove_license(user_1, license_object)

    LicenseHandler.remove_license(admin_1, license_object_2)
    licenses = License.objects.all()
    assert len(licenses) == 1
    assert licenses[0].id == license_object.id
    license_users = LicenseUser.objects.all()
    assert len(license_users) == 1
    assert license_users[0].user_id == user_1.id
    assert license_users[0].license_id == license_object.id


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
@patch("baserow_premium.license.handler.broadcast_to_users")
def test_add_user_to_license(mock_broadcast_to_users, data_fixture):
    with freeze_time("2021-09-01 12:00"):
        user_1 = data_fixture.create_user()
        user_2 = data_fixture.create_user()
        admin_1 = data_fixture.create_user(is_staff=True)
        license_object = License.objects.create(license=VALID_ONE_SEAT_LICENSE.decode())

        with pytest.raises(IsNotAdminError):
            LicenseHandler.add_user_to_license(user_1, license_object, user_1)

        license_user = LicenseHandler.add_user_to_license(
            admin_1, license_object, user_1
        )

        assert license_user.user_id == user_1.id
        assert license_user.license_id == license_object.id

        mock_broadcast_to_users.delay.assert_called_once()
        args = mock_broadcast_to_users.delay.call_args
        assert args[0][0] == [user_1.id]
        assert args[0][1]["type"] == "user_data_updated"
        assert args[0][1]["user_data"] == {
            "active_licenses": {"instance_wide": {"premium": True}}
        }

        with pytest.raises(UserAlreadyOnLicenseError):
            LicenseHandler.add_user_to_license(admin_1, license_object, user_1)

        with pytest.raises(NoSeatsLeftInLicenseError):
            LicenseHandler.add_user_to_license(admin_1, license_object, user_2)


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
@patch("baserow_premium.license.handler.broadcast_to_users")
def test_remove_user_from_license(mock_broadcast_to_users, data_fixture):
    with freeze_time("2021-09-01 12:00"):
        user_1 = data_fixture.create_user()
        admin_1 = data_fixture.create_user(is_staff=True)

        license_object = License.objects.create(license=VALID_ONE_SEAT_LICENSE.decode())
        LicenseUser.objects.create(license=license_object, user=user_1)

        with pytest.raises(IsNotAdminError):
            LicenseHandler.remove_user_from_license(user_1, license_object, user_1)

        with transaction.atomic():
            LicenseHandler.remove_user_from_license(admin_1, license_object, user_1)

        assert LicenseUser.objects.all().count() == 0

        mock_broadcast_to_users.delay.assert_called_once()
        args = mock_broadcast_to_users.delay.call_args
        assert args[0][0] == [user_1.id]
        assert args[0][1]["type"] == "user_data_updated"
        assert args[0][1]["user_data"] == {
            "active_licenses": {"instance_wide": {"premium": False}}
        }


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
@patch("baserow_premium.license.handler.broadcast_to_users")
def test_fill_remaining_seats_in_license(mock_broadcast_to_users, data_fixture):
    with freeze_time("2021-09-01 12:00"):
        user_1 = data_fixture.create_user(email="user1@baserow.io")
        user_2 = data_fixture.create_user(email="user2@baserow.io")
        user_3 = data_fixture.create_user(email="user3@baserow.io")
        user_4 = data_fixture.create_user(email="user4@baserow.io")
        admin_1 = data_fixture.create_user(is_staff=True, email="admin@baserow.io")

        license_object = License.objects.create(license=VALID_TWO_SEAT_LICENSE.decode())
        LicenseUser.objects.create(license=license_object, user=user_1)

        with pytest.raises(IsNotAdminError):
            LicenseHandler.fill_remaining_seats_of_license(user_1, license_object)

        LicenseHandler.fill_remaining_seats_of_license(admin_1, license_object)
        license_users = LicenseUser.objects.filter(license=license_object).order_by(
            "user_id"
        )
        assert len(license_users) == 2
        assert license_users[0].license_id == license_object.id
        assert license_users[0].user_id == user_1.id
        assert license_users[1].license_id == license_object.id
        assert license_users[1].user_id == admin_1.id
        mock_broadcast_to_users.delay.assert_called_once()
        args = mock_broadcast_to_users.delay.call_args
        assert len(args[0][0]) == 1
        assert args[0][0][0] == admin_1.id
        assert args[0][1]["type"] == "user_data_updated"
        assert args[0][1]["user_data"] == {
            "active_licenses": {"instance_wide": {"premium": True}}
        }

        license_object_2 = License.objects.create(
            license=VALID_ONE_SEAT_LICENSE.decode()
        )
        created_license_users = LicenseHandler.fill_remaining_seats_of_license(
            admin_1, license_object_2
        )
        assert len(created_license_users) == 1
        # We expect user 2 to be added because user_1 and admin_1 are already on
        # another license.
        assert created_license_users[0].license_id == license_object_2.id
        assert created_license_users[0].user_id == user_2.id
        assert LicenseUser.objects.all().count() == 3
        license_users = LicenseUser.objects.filter(license=license_object_2).order_by(
            "user_id"
        )
        assert len(license_users) == 1
        assert license_users[0].license_id == license_object_2.id
        assert license_users[0].user_id == user_2.id


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
@patch("baserow_premium.license.handler.broadcast_to_users")
def test_fill_remaining_seats_in_license_admin_already_on_license(
    mock_broadcast_to_users, data_fixture
):
    with freeze_time("2021-09-01 12:00"):
        user_1 = data_fixture.create_user()
        user_2 = data_fixture.create_user()
        data_fixture.create_user()
        admin_1 = data_fixture.create_user(is_staff=True)

        license_object = License.objects.create(license=VALID_TWO_SEAT_LICENSE.decode())
        LicenseUser.objects.create(license=license_object, user=user_1)
        LicenseHandler.add_user_to_license(admin_1, license_object, admin_1)
        LicenseHandler.fill_remaining_seats_of_license(admin_1, license_object)
        license_users = LicenseUser.objects.filter(license=license_object).order_by(
            "user_id"
        )
        assert len(license_users) == 2
        assert license_users[0].license_id == license_object.id
        assert license_users[0].user_id == user_1.id
        assert license_users[1].license_id == license_object.id
        assert license_users[1].user_id == admin_1.id


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
@patch("baserow_premium.license.handler.broadcast_to_users")
def test_remove_all_users_from_license(mock_broadcast_to_users, data_fixture):
    with freeze_time("2021-09-01 12:00"):
        user_1 = data_fixture.create_user()
        user_2 = data_fixture.create_user()
        admin_1 = data_fixture.create_user(is_staff=True)

        license_object = License.objects.create(license=VALID_TWO_SEAT_LICENSE.decode())
        LicenseUser.objects.create(license=license_object, user=user_1)
        license_object_2 = License.objects.create(
            license=VALID_TWO_SEAT_LICENSE.decode()
        )
        LicenseUser.objects.create(license=license_object_2, user=user_1)
        LicenseUser.objects.create(license=license_object_2, user=user_2)

        with pytest.raises(IsNotAdminError):
            LicenseHandler.remove_all_users_from_license(user_1, license_object)

        LicenseHandler.remove_all_users_from_license(admin_1, license_object_2)
        license_users = LicenseUser.objects.all()
        assert len(license_users) == 1
        assert license_users[0].license_id == license_object.id
        assert license_users[0].user_id == user_1.id
        assert LicenseUser.objects.all().count() == 1

        mock_broadcast_to_users.delay.assert_called_once()
        args = mock_broadcast_to_users.delay.call_args
        assert len(args[0][0]) == 2
        assert user_1.id in args[0][0]
        assert user_2.id in args[0][0]
        assert args[0][1]["type"] == "user_data_updated"
        assert args[0][1]["user_data"] == {
            "active_licenses": {"instance_wide": {"premium": False}}
        }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_check_active_premium_license_for_workspace_with_license_pretending_to_be_site_wide(
    data_fixture,
):
    user_in_license = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user_in_license)
    license = License.objects.create(
        license=VALID_TWO_SEAT_LICENSE.decode(), cached_untrusted_instance_wide=True
    )
    LicenseUser.objects.create(license=license, user=user_in_license)

    with freeze_time("2021-08-01 12:00"):
        with pytest.raises(FeaturesNotAvailableError):
            LicenseHandler.raise_if_user_doesnt_have_feature(
                PREMIUM, user_in_license, workspace
            )

    with freeze_time("2021-09-01 12:00"):
        with pytest.raises(FeaturesNotAvailableError):
            LicenseHandler.raise_if_user_doesnt_have_feature(
                PREMIUM, user_in_license, workspace
            )

    with freeze_time("2021-09-01 12:00"):
        assert not LicenseHandler.instance_has_feature(PREMIUM)
        assert not LicenseHandler.user_has_feature_instance_wide(
            PREMIUM, user_in_license
        )


@pytest.mark.django_db(transaction=True)
@override_settings(DEBUG=True)
def test_add_active_licenses_to_settings(api_client, data_fixture):
    with freeze_time("2021-07-01 12:00"):
        License.objects.create(
            license=VALID_TWO_SEAT_LICENSE.decode(), cached_untrusted_instance_wide=True
        )
        License.objects.create(
            license=VALID_ENTERPRISE_FIVE_SEAT_LICENSE.decode(),
            cached_untrusted_instance_wide=True,
        )

        response = api_client.get(reverse("api:settings:get"))
        assert response.status_code == HTTP_200_OK
        response_json = response.json()
        assert len(response_json.keys()) > 1
        assert response_json["instance_wide_licenses"] == {"enterprise": True}


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch("baserow_premium.license.registries.BuilderHandler.aggregate_user_source_counts")
def test_premium_license_builder_usage_license_extra_info(
    mock_aggregate_user_source_counts, premium_data_fixture
):
    # We have a single premium license, with 5 application users taken.
    mock_aggregate_user_source_counts.return_value = 5
    first_license = premium_data_fixture.create_premium_license(
        license=VALID_PREMIUM_TEN_SEAT_TEN_APP_USER_LICENSE.decode()
    )
    with local_cache.context():
        assert LicenseHandler.collect_extra_license_info(first_license) == {
            "id": first_license.license_id,
            "seats_taken": 0,
            "free_users_count": 0,
            "highest_role_per_user_id": {},
            "application_users_taken": 5,
        }

    # Introduce a second premium license, so we now have 25 application
    # users available, but now our application users taken is 30.
    mock_aggregate_user_source_counts.return_value = 30
    second_license = premium_data_fixture.create_premium_license(
        license=VALID_PREMIUM_5_SEAT_15_APP_USER_LICENSE.decode()
    )

    with local_cache.context():
        # Re-check the first license, its `application_users_taken`
        # count is the `application_users` count.
        assert LicenseHandler.collect_extra_license_info(first_license) == {
            "id": first_license.license_id,
            "seats_taken": 0,
            "free_users_count": 0,
            "highest_role_per_user_id": {},
            "application_users_taken": 10,
        }
        # The second license `application_users_taken` count overflows.
        assert LicenseHandler.collect_extra_license_info(second_license) == {
            "id": second_license.license_id,
            "seats_taken": 0,
            "free_users_count": 0,
            "highest_role_per_user_id": {},
            "application_users_taken": 20,
        }

    first_license.delete()

    with local_cache.context():
        # An expired license reports an application user usage of 0.
        expired_license = premium_data_fixture.create_premium_license(
            license=INVALID_PREMIUM_FIVE_SEAT_10_APP_USER_EXPIRED_LICENSE.decode()
        )
        assert LicenseHandler.collect_extra_license_info(expired_license) == {
            "id": expired_license.license_id,
            "seats_taken": 0,
            "free_users_count": 0,
            "highest_role_per_user_id": {},
            "application_users_taken": 0,
        }
        # The second license is now the only active license, so it reports the
        # full application user usage, which overflows.
        assert LicenseHandler.collect_extra_license_info(second_license) == {
            "id": second_license.license_id,
            "seats_taken": 0,
            "free_users_count": 0,
            "highest_role_per_user_id": {},
            "application_users_taken": 30,
        }
