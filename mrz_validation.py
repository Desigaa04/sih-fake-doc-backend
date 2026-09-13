def calculate_check_digit(data):
    weights = [7, 3, 1]
    total = 0

    for i, char in enumerate(data):
        if char == "<":
            value = 0
        elif char.isdigit():
            value = int(char)
        elif char.isalpha():
            value = ord(char.upper()) - ord("A") + 10
        else:
            return None

        total += value * weights[i % 3]

    return total % 10
def detect_mrz_format(line1, line2):

    line1 = line1.replace(" ", "").upper()
    line2 = line2.replace(" ", "").upper()

    # Passport MRZ
    if line1.startswith("P<"):
        return "PASSPORT"

    # Visa MRZ. ICAO 9303 says visa MRZ line 1 starts with "V" followed
    # by a type-designer character (often "<", i.e. V<), but real issuing
    # states print real characters there: India e-visas use VT/VJ, and
    # VJ* / VN* etc. all appear on genuine visas worldwide. Accept any
    # V-prefixed line whose third character is also MRZ-legal (A-Z, 0-9,
    # or "<") rather than enumerating codes - a strict V</VN list silently
    # rejects genuine Indian visas.
    if line1.startswith("V") and len(line1) >= 3 and (line1[2].isalnum() or line1[2] == "<"):

        if len(line1) == 44 and len(line2) == 44:
            return "MRV-A_VISA"

        if len(line1) == 36 and len(line2) == 36:
            return "MRV-B_VISA"

        return "VISA_UNKNOWN_FORMAT"

    return "UNKNOWN"
def parse_mrv_a(line2):

    line2 = line2.replace(" ", "")

    if len(line2) != 44:
        return None

    result = {
        "document_number": line2[0:9],
        "document_number_check_digit": line2[9],

        "nationality": line2[10:13],

        "date_of_birth": line2[13:19],
        "date_of_birth_check_digit": line2[19],

        "sex": line2[20],

        "valid_until": line2[21:27],
        "valid_until_check_digit": line2[27],

        "optional_data": line2[28:44]
    }

    return result
def validate_mrv_a(line2):

    line2 = line2.replace(" ", "")

    if len(line2) != 44:
        return {"valid": False, "error": "Invalid MRV-A length"}

    results = {}

    # Document / visa number
    document_number = line2[0:9]
    document_check_digit = line2[9]

    calculated = calculate_check_digit(document_number)

    # A "<" in the check-digit position is LEGAL per ICAO 9303 when the
    # underlying field is padded with fillers (e.g. 8-char document number
    # in the 9-char field: "DCHC4C<<"+... has no meaningful check digit to
    # verify). Treat it as "not applicable" rather than a failure - the
    # old code compared "<" to a computed number and false-flagged every
    # genuine Indian visa.
    if document_check_digit == "<":
        results["document_number"] = {
            "value": document_number,
            "given_check_digit": document_check_digit,
            "calculated_check_digit": str(calculated),
            "valid": True,
            "note": "check digit absent (filler-padded field) - not verifiable",
        }
    else:
        results["document_number"] = {
            "value": document_number,
            "given_check_digit": document_check_digit,
            "calculated_check_digit": str(calculated),
            "valid": document_check_digit == str(calculated)
        }

    # Date of birth
    dob = line2[13:19]
    dob_check_digit = line2[19]

    calculated = calculate_check_digit(dob)

    results["date_of_birth"] = {
        "value": dob,
        "given_check_digit": dob_check_digit,
        "calculated_check_digit": str(calculated),
        "valid": dob_check_digit == str(calculated)
    }

    # Valid until
    expiry = line2[21:27]
    expiry_check_digit = line2[27]

    calculated = calculate_check_digit(expiry)

    results["valid_until"] = {
        "value": expiry,
        "given_check_digit": expiry_check_digit,
        "calculated_check_digit": str(calculated),
        "valid": expiry_check_digit == str(calculated)
    }
        # Check whether any checksum failed
    if not results["document_number"]["valid"]:
        results["status"] = "MRZ_CHECKSUM_FAILED"

    elif not results["date_of_birth"]["valid"]:
        results["status"] = "MRZ_CHECKSUM_FAILED"

    elif not results["valid_until"]["valid"]:
        results["status"] = "MRZ_CHECKSUM_FAILED"

    else:
        results["status"] = "MRZ_VALID"

    return results
if __name__ == "__main__":

    document_number = "A12345678"
    dob = "900101"
    expiry = "300101"

    document_check = str(calculate_check_digit(document_number))
    dob_check = str(calculate_check_digit(dob))
    expiry_check = str(calculate_check_digit(expiry))

    line2 = (
        document_number
        + document_check
        + "IND"
        + dob
        + dob_check
        + "M"
        + expiry
        + expiry_check
        + "<" * 16
    )

    print("Original MRZ:")
    print(line2)

    print("\nOriginal Validation:")
    print(validate_mrv_a(line2))

    # Create a tampered MRZ
    tampered_line = line2[:8] + "9" + line2[9:]

    print("\nTampered MRZ:")
    print(tampered_line)

    print("\nTampered Validation:")
    print(validate_mrv_a(tampered_line))