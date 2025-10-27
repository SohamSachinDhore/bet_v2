"""
Family Pana Table Data
Structure: 3 family groups, 11 columns each
Numbers in the same column within a group belong to the same family
Column 11 has no header (special column)
"""

# Family Pana Table Structure
FAMILY_PANA_TABLE = {
    # Column headers (11th column has no header, marked as None)
    'columns': [1, 6, 2, 7, 3, 8, 4, 9, 5, 0, None],

    # Group 1: Rows 1-8 (same cell column-wise)
    'group1': [
        [128, 245, 129, 345, 120, 139, 130, 239, 140, 230, 227],  # Row1
        [137, 290, 147, 390, 157, 148, 158, 248, 159, 258, 277],  # Row2
        [236, 470, 246, 480, 256, 346, 356, 347, 456, 357, 222],  # Row3
        [678, 579, 679, 589, 670, 689, 680, 789, 690, 780, 777],  # Row4
        [123, 240, 124, 340, 125, 134, 135, 234, 145, 235, 449],  # Row5
        [178, 259, 179, 359, 170, 189, 180, 289, 190, 280, 499],  # Row6
        [268, 457, 269, 458, 260, 369, 360, 379, 460, 370, 444],  # Row7
        [367, 790, 467, 890, 567, 468, 568, 478, 569, 578, 999],  # Row8
    ],

    # Group 2: Rows 9-14 (same cell column-wise)
    'group2': [
        [146, 380, 138, 156, 238, 247, 167, 257, 168, 249, 166],  # Row9
        [119, 335, 336, 110, 337, 229, 112, 220, 113, 447, 116],  # Row10
        [669, 588, 688, 660, 788, 779, 266, 770, 366, 799, 111],  # Row11
        [169, 358, 368, 160, 378, 279, 126, 270, 136, 479, 666],  # Row12
        [114, 330, 133, 115, 233, 224, 117, 225, 118, 244, 338],  # Row13
        [466, 880, 188, 566, 288, 477, 667, 577, 668, 299, 388],  # Row14
    ],

    # Group 3: Rows 15-20 (same cell column-wise)
    'group3': [
        [489, 560, 237, 570, 490, 580, 149, 590, 267, 348, 888],  # Row15
        [344, 100, 228, 200, 445, 300, 446, 400, 122, 339, 333],  # Row16
        [399, 155, 778, 255, 599, 355, 699, 455, 177, 889, 500],  # Row17
        [349, 150, 278, 250, 459, 350, 469, 450, 127, 389, 550],  # Row18
        [448, 556, 223, 557, 440, 558, 144, 559, 226, 334, 555],  # Row19
        [899, 600, 377, 700, 990, 800, 199, 900, 677, 488, 0],    # Row20
    ]
}


def build_family_lookup():
    """
    Build a lookup dictionary mapping each reference number to its family members.

    Returns:
        Dict[int, List[int]] - {reference_number: [all_family_members_including_self]}
    """
    family_lookup = {}

    # Process each group
    for group_name in ['group1', 'group2', 'group3']:
        group = FAMILY_PANA_TABLE[group_name]

        # Process each column (now 11 columns)
        for col_idx in range(11):
            # Extract all numbers in this column
            column_numbers = [row[col_idx] for row in group]

            # Map each number to the complete family
            for number in column_numbers:
                family_lookup[number] = column_numbers

    return family_lookup


def get_family_members(reference_number: int):
    """
    Get all family members for a given reference number.

    Args:
        reference_number: The pana number to lookup

    Returns:
        List[int] - All family members (including the reference number itself)
        Returns empty list if not found
    """
    lookup = build_family_lookup()
    return lookup.get(reference_number, [])


# Pre-built lookup for quick access
FAMILY_LOOKUP = build_family_lookup()


if __name__ == '__main__':
    # Test the lookup
    print("=== Family Pana Table Tests ===\n")

    test_cases = [678, 146, 489, 128, 999]

    for test_num in test_cases:
        family = get_family_members(test_num)
        if family:
            print(f"Number: {test_num}")
            print(f"Family: {family}")
            print(f"Count: {len(family)} members")
            print()
        else:
            print(f"Number: {test_num} - NOT FOUND")
            print()
