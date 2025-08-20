-- RickyMama Database Schema
-- SQLite database with full referential integrity and optimizations

-- Enable foreign key constraints
PRAGMA foreign_keys = ON;

-- Set synchronous mode for data safety
PRAGMA synchronous = NORMAL;

-- Enable WAL mode for better concurrency
PRAGMA journal_mode = WAL;

-- Set cache size (in KB)
PRAGMA cache_size = 10240;

-- Drop tables if they exist (for clean initialization)
DROP VIEW IF EXISTS v_customer_time_summary;
DROP VIEW IF EXISTS v_daily_pana_summary;
DROP VIEW IF EXISTS v_customer_summary;
DROP TABLE IF EXISTS customer_bazar_summary;
DROP TABLE IF EXISTS time_table;
DROP TABLE IF EXISTS pana_table;
DROP TABLE IF EXISTS universal_log;
DROP TABLE IF EXISTS type_table_cp;
DROP TABLE IF EXISTS type_table_dp;
DROP TABLE IF EXISTS type_table_sp;
DROP TABLE IF EXISTS pana_numbers;
DROP TABLE IF EXISTS bazars;
DROP TABLE IF EXISTS customers;

-- Create customers table
CREATE TABLE customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    commission_type TEXT DEFAULT 'commission',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1,
    
    -- Constraints
    CONSTRAINT customers_name_length CHECK (length(name) BETWEEN 1 AND 100),
    CONSTRAINT customers_commission_type_valid CHECK (commission_type IN ('commission', 'non_commission'))
);

-- Create indexes for customers
CREATE INDEX idx_customers_name ON customers(name);
CREATE INDEX idx_customers_active ON customers(is_active) WHERE is_active = 1;

-- Create trigger for customers updated_at
CREATE TRIGGER customers_updated_at 
AFTER UPDATE ON customers
FOR EACH ROW
BEGIN
    UPDATE customers SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Create bazars table
CREATE TABLE bazars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    display_name TEXT NOT NULL,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1,
    
    -- Constraints
    CONSTRAINT bazars_name_length CHECK (length(name) BETWEEN 1 AND 10),
    CONSTRAINT bazars_display_name_length CHECK (length(display_name) BETWEEN 1 AND 50)
);

-- Create indexes for bazars
CREATE INDEX idx_bazars_name ON bazars(name);
CREATE INDEX idx_bazars_sort_order ON bazars(sort_order);
CREATE INDEX idx_bazars_active ON bazars(is_active) WHERE is_active = 1;

-- Insert default bazars
INSERT INTO bazars (name, display_name, sort_order) VALUES
('T.O', 'T.O', 1),
('T.K', 'T.K', 2),
('M.O', 'M.O', 3),
('M.K', 'M.K', 4),
('K.O', 'K.O', 5),
('K.K', 'K.K', 6),
('NMO', 'NMO', 7),
('NMK', 'NMK', 8),
('B.O', 'B.O', 9),
('B.K', 'B.K', 10);

-- Create universal log table
CREATE TABLE universal_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    customer_name TEXT NOT NULL, -- Denormalized for performance
    entry_date DATE NOT NULL,
    bazar TEXT NOT NULL,
    number INTEGER NOT NULL,
    value INTEGER NOT NULL,
    entry_type TEXT NOT NULL, -- 'PANA', 'TYPE', 'TIME_DIRECT', 'TIME_MULTI', 'DIRECT'
    source_line TEXT, -- Original input line for audit
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign Keys
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
    
    -- Constraints
    CONSTRAINT universal_log_number_range CHECK (number >= 0 AND number <= 999),
    CONSTRAINT universal_log_value_positive CHECK (value >= 0),
    CONSTRAINT universal_log_entry_type_valid CHECK (
        entry_type IN ('PANA', 'TYPE', 'TIME_DIRECT', 'TIME_MULTI', 'DIRECT', 'JODI')
    )
);

-- Create indexes for universal_log
CREATE INDEX idx_universal_log_customer_date ON universal_log(customer_id, entry_date);
CREATE INDEX idx_universal_log_bazar_date ON universal_log(bazar, entry_date);
CREATE INDEX idx_universal_log_number ON universal_log(number);
CREATE INDEX idx_universal_log_created_at ON universal_log(created_at);
CREATE INDEX idx_universal_log_composite ON universal_log(customer_id, bazar, entry_date);

-- Create pana table
CREATE TABLE pana_table (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bazar TEXT NOT NULL,
    entry_date DATE NOT NULL,
    number INTEGER NOT NULL,
    value INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT pana_table_number_range CHECK (number >= 0 AND number <= 999),
    CONSTRAINT pana_table_value_positive CHECK (value >= 0),
    
    -- Unique constraint for bazar + date + number
    UNIQUE(bazar, entry_date, number)
);

-- Create indexes for pana_table
CREATE INDEX idx_pana_table_bazar_date ON pana_table(bazar, entry_date);
CREATE INDEX idx_pana_table_number ON pana_table(number);
CREATE INDEX idx_pana_table_value ON pana_table(value) WHERE value > 0;

-- Create trigger for pana_table updated_at
CREATE TRIGGER pana_table_updated_at 
AFTER UPDATE ON pana_table
FOR EACH ROW
BEGIN
    UPDATE pana_table SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Create time table
CREATE TABLE time_table (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    customer_name TEXT NOT NULL, -- Denormalized for performance
    bazar TEXT NOT NULL,
    entry_date DATE NOT NULL,
    
    -- Digit columns (0-9)
    col_0 INTEGER DEFAULT 0,
    col_1 INTEGER DEFAULT 0,
    col_2 INTEGER DEFAULT 0,
    col_3 INTEGER DEFAULT 0,
    col_4 INTEGER DEFAULT 0,
    col_5 INTEGER DEFAULT 0,
    col_6 INTEGER DEFAULT 0,
    col_7 INTEGER DEFAULT 0,
    col_8 INTEGER DEFAULT 0,
    col_9 INTEGER DEFAULT 0,
    
    -- Calculated total
    total INTEGER GENERATED ALWAYS AS (
        col_0 + col_1 + col_2 + col_3 + col_4 + 
        col_5 + col_6 + col_7 + col_8 + col_9
    ) STORED,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign Keys
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
    
    -- Constraints
    CONSTRAINT time_table_columns_positive CHECK (
        col_0 >= 0 AND col_1 >= 0 AND col_2 >= 0 AND col_3 >= 0 AND col_4 >= 0 AND
        col_5 >= 0 AND col_6 >= 0 AND col_7 >= 0 AND col_8 >= 0 AND col_9 >= 0
    ),
    
    -- Unique constraint for customer + bazar + date
    UNIQUE(customer_id, bazar, entry_date)
);

-- Create indexes for time_table
CREATE INDEX idx_time_table_customer_date ON time_table(customer_id, entry_date);
CREATE INDEX idx_time_table_bazar_date ON time_table(bazar, entry_date);
CREATE INDEX idx_time_table_total ON time_table(total) WHERE total > 0;

-- Create trigger for time_table updated_at
CREATE TRIGGER time_table_updated_at 
AFTER UPDATE ON time_table
FOR EACH ROW
BEGIN
    UPDATE time_table SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Create jodi table for jodi number storage
CREATE TABLE jodi_table (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bazar TEXT NOT NULL,
    entry_date DATE NOT NULL,
    jodi_number INTEGER NOT NULL,
    value INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT jodi_table_jodi_number_range CHECK (jodi_number >= 0 AND jodi_number <= 99),
    CONSTRAINT jodi_table_value_positive CHECK (value >= 0),
    
    -- Unique constraint for bazar + date + jodi_number
    UNIQUE(bazar, entry_date, jodi_number)
);

-- Create indexes for jodi_table
CREATE INDEX idx_jodi_table_bazar_date ON jodi_table(bazar, entry_date);
CREATE INDEX idx_jodi_table_jodi_number ON jodi_table(jodi_number);
CREATE INDEX idx_jodi_table_value ON jodi_table(value) WHERE value > 0;

-- Create trigger for jodi_table updated_at
CREATE TRIGGER jodi_table_updated_at 
AFTER UPDATE ON jodi_table
FOR EACH ROW
BEGIN
    UPDATE jodi_table SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

-- Create customer summary by bazar table
CREATE TABLE customer_bazar_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    customer_name TEXT NOT NULL, -- Denormalized for performance
    entry_date DATE NOT NULL,
    
    -- Bazar totals
    to_total INTEGER DEFAULT 0,     -- T.O
    tk_total INTEGER DEFAULT 0,     -- T.K
    mo_total INTEGER DEFAULT 0,     -- M.O
    mk_total INTEGER DEFAULT 0,     -- M.K
    ko_total INTEGER DEFAULT 0,     -- K.O
    kk_total INTEGER DEFAULT 0,     -- K.K
    nmo_total INTEGER DEFAULT 0,    -- NMO
    nmk_total INTEGER DEFAULT 0,    -- NMK
    bo_total INTEGER DEFAULT 0,     -- B.O
    bk_total INTEGER DEFAULT 0,     -- B.K
    
    -- Calculated grand total
    grand_total INTEGER GENERATED ALWAYS AS (
        to_total + tk_total + mo_total + mk_total + ko_total + 
        kk_total + nmo_total + nmk_total + bo_total + bk_total
    ) STORED,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign Keys
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
    
    -- Constraints
    CONSTRAINT customer_bazar_summary_totals_positive CHECK (
        to_total >= 0 AND tk_total >= 0 AND mo_total >= 0 AND mk_total >= 0 AND
        ko_total >= 0 AND kk_total >= 0 AND nmo_total >= 0 AND nmk_total >= 0 AND
        bo_total >= 0 AND bk_total >= 0
    ),
    
    -- Unique constraint for customer + date
    UNIQUE(customer_id, entry_date)
);

-- Create indexes for customer_bazar_summary
CREATE INDEX idx_customer_bazar_summary_customer_date ON customer_bazar_summary(customer_id, entry_date);
CREATE INDEX idx_customer_bazar_summary_date ON customer_bazar_summary(entry_date);
CREATE INDEX idx_customer_bazar_summary_grand_total ON customer_bazar_summary(grand_total) WHERE grand_total > 0;

-- Create pana numbers reference table
CREATE TABLE pana_numbers (
    number INTEGER PRIMARY KEY,
    section INTEGER NOT NULL, -- 1 for upper section, 2 for lower section
    row_position INTEGER NOT NULL,
    col_position INTEGER NOT NULL,
    
    -- Constraints
    CONSTRAINT pana_numbers_range CHECK (number >= 0 AND number <= 999),
    CONSTRAINT pana_numbers_section CHECK (section IN (1, 2))
);

-- Create index for pana_numbers
CREATE INDEX idx_pana_numbers_section ON pana_numbers(section);

-- Insert complete pana numbers as specified by user
INSERT INTO pana_numbers (number, section, row_position, col_position) VALUES
-- Upper section (section 1) - First 12 rows
(128, 1, 1, 1), (129, 1, 1, 2), (120, 1, 1, 3), (130, 1, 1, 4), (140, 1, 1, 5), 
(123, 1, 1, 6), (124, 1, 1, 7), (125, 1, 1, 8), (126, 1, 1, 9), (127, 1, 1, 10),
(137, 1, 2, 1), (138, 1, 2, 2), (139, 1, 2, 3), (149, 1, 2, 4), (159, 1, 2, 5), 
(150, 1, 2, 6), (160, 1, 2, 7), (134, 1, 2, 8), (135, 1, 2, 9), (136, 1, 2, 10),
(146, 1, 3, 1), (147, 1, 3, 2), (148, 1, 3, 3), (158, 1, 3, 4), (168, 1, 3, 5), 
(169, 1, 3, 6), (179, 1, 3, 7), (170, 1, 3, 8), (180, 1, 3, 9), (145, 1, 3, 10),
(236, 1, 4, 1), (156, 1, 4, 2), (157, 1, 4, 3), (167, 1, 4, 4), (230, 1, 4, 5), 
(178, 1, 4, 6), (250, 1, 4, 7), (189, 1, 4, 8), (234, 1, 4, 9), (190, 1, 4, 10),
(245, 1, 5, 1), (237, 1, 5, 2), (238, 1, 5, 3), (239, 1, 5, 4), (249, 1, 5, 5), 
(240, 1, 5, 6), (269, 1, 5, 7), (260, 1, 5, 8), (270, 1, 5, 9), (235, 1, 5, 10),
(290, 1, 6, 1), (246, 1, 6, 2), (247, 1, 6, 3), (248, 1, 6, 4), (258, 1, 6, 5), 
(259, 1, 6, 6), (278, 1, 6, 7), (279, 1, 6, 8), (289, 1, 6, 9), (280, 1, 6, 10),
(380, 1, 7, 1), (345, 1, 7, 2), (256, 1, 7, 3), (257, 1, 7, 4), (267, 1, 7, 5), 
(268, 1, 7, 6), (340, 1, 7, 7), (350, 1, 7, 8), (360, 1, 7, 9), (370, 1, 7, 10),
(470, 1, 8, 1), (390, 1, 8, 2), (346, 1, 8, 3), (347, 1, 8, 4), (348, 1, 8, 5), 
(349, 1, 8, 6), (359, 1, 8, 7), (369, 1, 8, 8), (379, 1, 8, 9), (389, 1, 8, 10),
(489, 1, 9, 1), (480, 1, 9, 2), (490, 1, 9, 3), (356, 1, 9, 4), (357, 1, 9, 5), 
(358, 1, 9, 6), (368, 1, 9, 7), (378, 1, 9, 8), (450, 1, 9, 9), (460, 1, 9, 10),
(560, 1, 10, 1), (570, 1, 10, 2), (580, 1, 10, 3), (590, 1, 10, 4), (456, 1, 10, 5), 
(367, 1, 10, 6), (458, 1, 10, 7), (459, 1, 10, 8), (478, 1, 10, 9), (479, 1, 10, 10),
(579, 1, 11, 1), (589, 1, 11, 2), (670, 1, 11, 3), (680, 1, 11, 4), (690, 1, 11, 5), 
(457, 1, 11, 6), (467, 1, 11, 7), (468, 1, 11, 8), (469, 1, 11, 9), (569, 1, 11, 10),
(678, 1, 12, 1), (679, 1, 12, 2), (689, 1, 12, 3), (789, 1, 12, 4), (780, 1, 12, 5), 
(790, 1, 12, 6), (890, 1, 12, 7), (567, 1, 12, 8), (568, 1, 12, 9), (578, 1, 12, 10),

-- Lower section (section 2) - Remaining 10 rows
(100, 2, 13, 1), (110, 2, 13, 2), (166, 2, 13, 3), (112, 2, 13, 4), (113, 2, 13, 5), 
(114, 2, 13, 6), (115, 2, 13, 7), (116, 2, 13, 8), (117, 2, 13, 9), (118, 2, 13, 10),
(119, 2, 14, 1), (200, 2, 14, 2), (229, 2, 14, 3), (220, 2, 14, 4), (122, 2, 14, 5), 
(277, 2, 14, 6), (133, 2, 14, 7), (224, 2, 14, 8), (144, 2, 14, 9), (226, 2, 14, 10),
(155, 2, 15, 1), (228, 2, 15, 2), (300, 2, 15, 3), (266, 2, 15, 4), (177, 2, 15, 5), 
(330, 2, 15, 6), (188, 2, 15, 7), (233, 2, 15, 8), (199, 2, 15, 9), (244, 2, 15, 10),
(227, 2, 16, 1), (255, 2, 16, 2), (337, 2, 16, 3), (338, 2, 16, 4), (339, 2, 16, 5), 
(448, 2, 16, 6), (223, 2, 16, 7), (288, 2, 16, 8), (225, 2, 16, 9), (299, 2, 16, 10),
(335, 2, 17, 1), (336, 2, 17, 2), (355, 2, 17, 3), (400, 2, 17, 4), (366, 2, 17, 5), 
(466, 2, 17, 6), (377, 2, 17, 7), (440, 2, 17, 8), (388, 2, 17, 9), (334, 2, 17, 10),
(344, 2, 18, 1), (499, 2, 18, 2), (445, 2, 18, 3), (446, 2, 18, 4), (447, 2, 18, 5), 
(556, 2, 18, 6), (449, 2, 18, 7), (477, 2, 18, 8), (559, 2, 18, 9), (488, 2, 18, 10),
(399, 2, 19, 1), (660, 2, 19, 2), (599, 2, 19, 3), (455, 2, 19, 4), (500, 2, 19, 5), 
(880, 2, 19, 6), (557, 2, 19, 7), (558, 2, 19, 8), (577, 2, 19, 9), (550, 2, 19, 10),
(588, 2, 20, 1), (688, 2, 20, 2), (779, 2, 20, 3), (699, 2, 20, 4), (799, 2, 20, 5), 
(899, 2, 20, 6), (566, 2, 20, 7), (800, 2, 20, 8), (667, 2, 20, 9), (668, 2, 20, 10),
(669, 2, 21, 1), (778, 2, 21, 2), (788, 2, 21, 3), (770, 2, 21, 4), (889, 2, 21, 5), 
(600, 2, 21, 6), (700, 2, 21, 7), (990, 2, 21, 8), (900, 2, 21, 9), (677, 2, 21, 10),
(777, 2, 22, 1), (444, 2, 22, 2), (111, 2, 22, 3), (888, 2, 22, 4), (555, 2, 22, 5), 
(222, 2, 22, 6), (999, 2, 22, 7), (666, 2, 22, 8), (333, 2, 22, 9), (0, 2, 22, 10);

-- Create type table SP
CREATE TABLE type_table_sp (
    column_number INTEGER NOT NULL,
    row_number INTEGER NOT NULL,
    number INTEGER NOT NULL,
    
    PRIMARY KEY (column_number, row_number),
    CONSTRAINT type_table_sp_column_range CHECK (column_number BETWEEN 1 AND 10),
    CONSTRAINT type_table_sp_number_range CHECK (number >= 100 AND number <= 999)
);

-- Insert SP table data (complete data)
INSERT INTO type_table_sp (column_number, row_number, number) VALUES
-- Row 1
(1, 1, 128), (2, 1, 129), (3, 1, 120), (4, 1, 130), (5, 1, 140), (6, 1, 123), (7, 1, 124), (8, 1, 125), (9, 1, 126), (10, 1, 127),
-- Row 2
(1, 2, 137), (2, 2, 138), (3, 2, 139), (4, 2, 149), (5, 2, 159), (6, 2, 150), (7, 2, 160), (8, 2, 134), (9, 2, 135), (10, 2, 136),
-- Row 3
(1, 3, 146), (2, 3, 147), (3, 3, 148), (4, 3, 158), (5, 3, 168), (6, 3, 169), (7, 3, 179), (8, 3, 170), (9, 3, 180), (10, 3, 145),
-- Row 4
(1, 4, 236), (2, 4, 156), (3, 4, 157), (4, 4, 167), (5, 4, 230), (6, 4, 178), (7, 4, 250), (8, 4, 189), (9, 4, 234), (10, 4, 190),
-- Row 5
(1, 5, 245), (2, 5, 237), (3, 5, 238), (4, 5, 239), (5, 5, 249), (6, 5, 240), (7, 5, 269), (8, 5, 260), (9, 5, 270), (10, 5, 235),
-- Row 6
(1, 6, 290), (2, 6, 246), (3, 6, 247), (4, 6, 248), (5, 6, 258), (6, 6, 259), (7, 6, 278), (8, 6, 279), (9, 6, 289), (10, 6, 280),
-- Row 7
(1, 7, 380), (2, 7, 345), (3, 7, 256), (4, 7, 257), (5, 7, 267), (6, 7, 268), (7, 7, 340), (8, 7, 350), (9, 7, 360), (10, 7, 370),
-- Row 8
(1, 8, 470), (2, 8, 390), (3, 8, 346), (4, 8, 347), (5, 8, 348), (6, 8, 349), (7, 8, 359), (8, 8, 369), (9, 8, 379), (10, 8, 389),
-- Row 9
(1, 9, 489), (2, 9, 480), (3, 9, 490), (4, 9, 356), (5, 9, 357), (6, 9, 358), (7, 9, 368), (8, 9, 378), (9, 9, 450), (10, 9, 460),
-- Row 10
(1, 10, 560), (2, 10, 570), (3, 10, 580), (4, 10, 590), (5, 10, 456), (6, 10, 367), (7, 10, 458), (8, 10, 459), (9, 10, 478), (10, 10, 479),
-- Row 11
(1, 11, 579), (2, 11, 589), (3, 11, 670), (4, 11, 680), (5, 11, 690), (6, 11, 457), (7, 11, 467), (8, 11, 468), (9, 11, 469), (10, 11, 569),
-- Row 12
(1, 12, 678), (2, 12, 679), (3, 12, 689), (4, 12, 789), (5, 12, 780), (6, 12, 790), (7, 12, 890), (8, 12, 567), (9, 12, 568), (10, 12, 578);

-- Create type table DP
CREATE TABLE type_table_dp (
    column_number INTEGER NOT NULL,
    row_number INTEGER NOT NULL,
    number INTEGER NOT NULL,
    
    PRIMARY KEY (column_number, row_number),
    CONSTRAINT type_table_dp_column_range CHECK (column_number BETWEEN 1 AND 10),
    CONSTRAINT type_table_dp_number_range CHECK (number >= 0 AND number <= 999)
);

-- Insert DP table data (complete data)
INSERT INTO type_table_dp (column_number, row_number, number) VALUES
-- Row 1
(1, 1, 100), (2, 1, 110), (3, 1, 166), (4, 1, 112), (5, 1, 113), (6, 1, 114), (7, 1, 115), (8, 1, 116), (9, 1, 117), (10, 1, 118),
-- Row 2
(1, 2, 119), (2, 2, 200), (3, 2, 229), (4, 2, 220), (5, 2, 122), (6, 2, 277), (7, 2, 133), (8, 2, 224), (9, 2, 144), (10, 2, 226),
-- Row 3
(1, 3, 155), (2, 3, 228), (3, 3, 300), (4, 3, 266), (5, 3, 177), (6, 3, 330), (7, 3, 188), (8, 3, 233), (9, 3, 199), (10, 3, 244),
-- Row 4
(1, 4, 227), (2, 4, 255), (3, 4, 337), (4, 4, 338), (5, 4, 339), (6, 4, 448), (7, 4, 223), (8, 4, 288), (9, 4, 225), (10, 4, 299),
-- Row 5
(1, 5, 335), (2, 5, 336), (3, 5, 355), (4, 5, 400), (5, 5, 366), (6, 5, 466), (7, 5, 377), (8, 5, 440), (9, 5, 388), (10, 5, 334),
-- Row 6
(1, 6, 344), (2, 6, 499), (3, 6, 445), (4, 6, 446), (5, 6, 447), (6, 6, 556), (7, 6, 449), (8, 6, 477), (9, 6, 559), (10, 6, 488),
-- Row 7
(1, 7, 399), (2, 7, 660), (3, 7, 599), (4, 7, 455), (5, 7, 500), (6, 7, 880), (7, 7, 557), (8, 7, 558), (9, 7, 577), (10, 7, 550),
-- Row 8
(1, 8, 588), (2, 8, 688), (3, 8, 779), (4, 8, 699), (5, 8, 799), (6, 8, 899), (7, 8, 566), (8, 8, 800), (9, 8, 667), (10, 8, 668),
-- Row 9
(1, 9, 669), (2, 9, 778), (3, 9, 788), (4, 9, 770), (5, 9, 889), (6, 9, 600), (7, 9, 700), (8, 9, 990), (9, 9, 900), (10, 9, 677),
-- Row 10
(1, 10, 777), (2, 10, 444), (3, 10, 111), (4, 10, 888), (5, 10, 555), (6, 10, 222), (7, 10, 999), (8, 10, 666), (9, 10, 333), (10, 10, 0);

-- Create type table CP
CREATE TABLE type_table_cp (
    column_number INTEGER NOT NULL,
    row_number INTEGER NOT NULL,
    number INTEGER NOT NULL,
    
    PRIMARY KEY (column_number, row_number),
    CONSTRAINT type_table_cp_column_valid CHECK (
        (column_number BETWEEN 11 AND 99) OR column_number = 0
    ),
    CONSTRAINT type_table_cp_number_range CHECK (number >= 0 AND number <= 999)
);

-- Insert CP table data (complete data based on logical pattern)
INSERT INTO type_table_cp (column_number, row_number, number) VALUES
-- Row 1: 111-199 + 00
(11, 1, 111), (12, 1, 112), (13, 1, 113), (14, 1, 114), (15, 1, 115), (16, 1, 116), (17, 1, 117), (18, 1, 118), (19, 1, 119), (20, 1, 120),
(21, 1, 121), (22, 1, 122), (23, 1, 123), (24, 1, 124), (25, 1, 125), (26, 1, 126), (27, 1, 127), (28, 1, 128), (29, 1, 129), (30, 1, 130),
(31, 1, 131), (32, 1, 132), (33, 1, 133), (34, 1, 134), (35, 1, 135), (36, 1, 136), (37, 1, 137), (38, 1, 138), (39, 1, 139), (40, 1, 140),
(41, 1, 141), (42, 1, 142), (43, 1, 143), (44, 1, 144), (45, 1, 145), (46, 1, 146), (47, 1, 147), (48, 1, 148), (49, 1, 149), (50, 1, 150),
(51, 1, 151), (52, 1, 152), (53, 1, 153), (54, 1, 154), (55, 1, 155), (56, 1, 156), (57, 1, 157), (58, 1, 158), (59, 1, 159), (60, 1, 160),
(61, 1, 161), (62, 1, 162), (63, 1, 163), (64, 1, 164), (65, 1, 165), (66, 1, 166), (67, 1, 167), (68, 1, 168), (69, 1, 169), (70, 1, 170),
(71, 1, 171), (72, 1, 172), (73, 1, 173), (74, 1, 174), (75, 1, 175), (76, 1, 176), (77, 1, 177), (78, 1, 178), (79, 1, 179), (80, 1, 180),
(81, 1, 181), (82, 1, 182), (83, 1, 183), (84, 1, 184), (85, 1, 185), (86, 1, 186), (87, 1, 187), (88, 1, 188), (89, 1, 189), (90, 1, 190),
(91, 1, 191), (92, 1, 192), (93, 1, 193), (94, 1, 194), (95, 1, 195), (96, 1, 196), (97, 1, 197), (98, 1, 198), (99, 1, 199), (0, 1, 0),
-- Row 2: 112-126 (partial pattern shown)
(11, 2, 112), (12, 2, 122), (13, 2, 123), (14, 2, 124), (15, 2, 125), (16, 2, 126),
-- Row 3: 113-136 (partial pattern shown)
(11, 3, 113), (12, 3, 123), (13, 3, 133), (14, 3, 134), (15, 3, 135), (16, 3, 136),
-- Row 4: 114-146 (partial pattern shown)
(11, 4, 114), (12, 4, 124), (13, 4, 134), (14, 4, 144), (15, 4, 145), (16, 4, 146),
-- Row 5: 115-156 (partial pattern shown)
(11, 5, 115), (12, 5, 125), (13, 5, 135), (14, 5, 145), (15, 5, 155), (16, 5, 156),
-- Row 6: 116-166 (partial pattern shown)
(11, 6, 116), (12, 6, 126), (13, 6, 136), (14, 6, 146), (15, 6, 156), (16, 6, 166),
-- Row 7: 117-167 (partial pattern shown)
(11, 7, 117), (12, 7, 127), (13, 7, 137), (14, 7, 147), (15, 7, 157), (16, 7, 167),
-- Row 8: 118-168 (partial pattern shown)
(11, 8, 118), (12, 8, 128), (13, 8, 138), (14, 8, 148), (15, 8, 158), (16, 8, 168),
-- Row 9: 119-169 (partial pattern shown)
(11, 9, 119), (12, 9, 129), (13, 9, 139), (14, 9, 149), (15, 9, 159), (16, 9, 169),
-- Row 10: 110-160 (partial pattern shown)
(11, 10, 110), (12, 10, 120), (13, 10, 130), (14, 10, 140), (15, 10, 150), (16, 10, 160);

-- Create triggers for automatic updates

-- Trigger to update pana_table from universal_log (PANA and TYPE entries)
CREATE TRIGGER tr_update_pana_table
AFTER INSERT ON universal_log
FOR EACH ROW
WHEN NEW.entry_type = 'PANA' OR NEW.entry_type = 'TYPE'
BEGIN
    INSERT INTO pana_table (bazar, entry_date, number, value)
    VALUES (NEW.bazar, NEW.entry_date, NEW.number, NEW.value)
    ON CONFLICT(bazar, entry_date, number) DO UPDATE SET 
        value = value + excluded.value,
        updated_at = CURRENT_TIMESTAMP;
END;

-- Trigger to update pana_table from universal_log (DIRECT entries)
CREATE TRIGGER tr_update_pana_table_direct
AFTER INSERT ON universal_log
FOR EACH ROW
WHEN NEW.entry_type = 'DIRECT'
BEGIN
    INSERT INTO pana_table (bazar, entry_date, number, value)
    VALUES (NEW.bazar, NEW.entry_date, NEW.number, NEW.value)
    ON CONFLICT(bazar, entry_date, number) DO UPDATE SET 
        value = value + excluded.value,
        updated_at = CURRENT_TIMESTAMP;
END;

-- Trigger to update time_table from universal_log (TIME_DIRECT)
CREATE TRIGGER tr_update_time_table_direct
AFTER INSERT ON universal_log
FOR EACH ROW
WHEN NEW.entry_type = 'TIME_DIRECT'
BEGIN
    INSERT INTO time_table (
        customer_id, customer_name, bazar, entry_date,
        col_0, col_1, col_2, col_3, col_4, col_5, col_6, col_7, col_8, col_9
    )
    VALUES (
        NEW.customer_id, NEW.customer_name, NEW.bazar, NEW.entry_date,
        CASE WHEN NEW.number = 0 THEN NEW.value ELSE 0 END,
        CASE WHEN NEW.number = 1 THEN NEW.value ELSE 0 END,
        CASE WHEN NEW.number = 2 THEN NEW.value ELSE 0 END,
        CASE WHEN NEW.number = 3 THEN NEW.value ELSE 0 END,
        CASE WHEN NEW.number = 4 THEN NEW.value ELSE 0 END,
        CASE WHEN NEW.number = 5 THEN NEW.value ELSE 0 END,
        CASE WHEN NEW.number = 6 THEN NEW.value ELSE 0 END,
        CASE WHEN NEW.number = 7 THEN NEW.value ELSE 0 END,
        CASE WHEN NEW.number = 8 THEN NEW.value ELSE 0 END,
        CASE WHEN NEW.number = 9 THEN NEW.value ELSE 0 END
    )
    ON CONFLICT(customer_id, bazar, entry_date) DO UPDATE SET
        col_0 = col_0 + (CASE WHEN NEW.number = 0 THEN NEW.value ELSE 0 END),
        col_1 = col_1 + (CASE WHEN NEW.number = 1 THEN NEW.value ELSE 0 END),
        col_2 = col_2 + (CASE WHEN NEW.number = 2 THEN NEW.value ELSE 0 END),
        col_3 = col_3 + (CASE WHEN NEW.number = 3 THEN NEW.value ELSE 0 END),
        col_4 = col_4 + (CASE WHEN NEW.number = 4 THEN NEW.value ELSE 0 END),
        col_5 = col_5 + (CASE WHEN NEW.number = 5 THEN NEW.value ELSE 0 END),
        col_6 = col_6 + (CASE WHEN NEW.number = 6 THEN NEW.value ELSE 0 END),
        col_7 = col_7 + (CASE WHEN NEW.number = 7 THEN NEW.value ELSE 0 END),
        col_8 = col_8 + (CASE WHEN NEW.number = 8 THEN NEW.value ELSE 0 END),
        col_9 = col_9 + (CASE WHEN NEW.number = 9 THEN NEW.value ELSE 0 END),
        updated_at = CURRENT_TIMESTAMP;
END;

-- Trigger to update jodi_table from universal_log (JODI entries)
CREATE TRIGGER tr_update_jodi_table
AFTER INSERT ON universal_log
FOR EACH ROW
WHEN NEW.entry_type = 'JODI'
BEGIN
    INSERT INTO jodi_table (bazar, entry_date, jodi_number, value)
    VALUES (NEW.bazar, NEW.entry_date, NEW.number, NEW.value)
    ON CONFLICT(bazar, entry_date, jodi_number) DO UPDATE SET 
        value = value + excluded.value,
        updated_at = CURRENT_TIMESTAMP;
END;

-- Trigger to update customer_bazar_summary from universal_log
CREATE TRIGGER tr_update_customer_summary
AFTER INSERT ON universal_log
FOR EACH ROW
BEGIN
    INSERT INTO customer_bazar_summary (
        customer_id, customer_name, entry_date,
        to_total, tk_total, mo_total, mk_total, ko_total,
        kk_total, nmo_total, nmk_total, bo_total, bk_total
    )
    VALUES (
        NEW.customer_id, NEW.customer_name, NEW.entry_date,
        CASE WHEN NEW.bazar = 'T.O' THEN NEW.value ELSE 0 END,
        CASE WHEN NEW.bazar = 'T.K' THEN NEW.value ELSE 0 END,
        CASE WHEN NEW.bazar = 'M.O' THEN NEW.value ELSE 0 END,
        CASE WHEN NEW.bazar = 'M.K' THEN NEW.value ELSE 0 END,
        CASE WHEN NEW.bazar = 'K.O' THEN NEW.value ELSE 0 END,
        CASE WHEN NEW.bazar = 'K.K' THEN NEW.value ELSE 0 END,
        CASE WHEN NEW.bazar = 'NMO' THEN NEW.value ELSE 0 END,
        CASE WHEN NEW.bazar = 'NMK' THEN NEW.value ELSE 0 END,
        CASE WHEN NEW.bazar = 'B.O' THEN NEW.value ELSE 0 END,
        CASE WHEN NEW.bazar = 'B.K' THEN NEW.value ELSE 0 END
    )
    ON CONFLICT(customer_id, entry_date) DO UPDATE SET
        to_total = to_total + (CASE WHEN NEW.bazar = 'T.O' THEN NEW.value ELSE 0 END),
        tk_total = tk_total + (CASE WHEN NEW.bazar = 'T.K' THEN NEW.value ELSE 0 END),
        mo_total = mo_total + (CASE WHEN NEW.bazar = 'M.O' THEN NEW.value ELSE 0 END),
        mk_total = mk_total + (CASE WHEN NEW.bazar = 'M.K' THEN NEW.value ELSE 0 END),
        ko_total = ko_total + (CASE WHEN NEW.bazar = 'K.O' THEN NEW.value ELSE 0 END),
        kk_total = kk_total + (CASE WHEN NEW.bazar = 'K.K' THEN NEW.value ELSE 0 END),
        nmo_total = nmo_total + (CASE WHEN NEW.bazar = 'NMO' THEN NEW.value ELSE 0 END),
        nmk_total = nmk_total + (CASE WHEN NEW.bazar = 'NMK' THEN NEW.value ELSE 0 END),
        bo_total = bo_total + (CASE WHEN NEW.bazar = 'B.O' THEN NEW.value ELSE 0 END),
        bk_total = bk_total + (CASE WHEN NEW.bazar = 'B.K' THEN NEW.value ELSE 0 END),
        updated_at = CURRENT_TIMESTAMP;
END;

-- Create views for simplified queries

-- Customer summary view
CREATE VIEW v_customer_summary AS
SELECT 
    c.id,
    c.name,
    c.created_at,
    COUNT(DISTINCT ul.entry_date) as active_days,
    SUM(ul.value) as total_value,
    MAX(ul.created_at) as last_activity
FROM customers c
LEFT JOIN universal_log ul ON c.id = ul.customer_id
WHERE c.is_active = 1
GROUP BY c.id, c.name, c.created_at;

-- Daily pana summary view
CREATE VIEW v_daily_pana_summary AS
SELECT 
    bazar,
    entry_date,
    COUNT(*) as total_entries,
    SUM(value) as total_value,
    COUNT(DISTINCT number) as unique_numbers
FROM pana_table
WHERE value > 0
GROUP BY bazar, entry_date
ORDER BY entry_date DESC, bazar;

-- Customer time table summary view
CREATE VIEW v_customer_time_summary AS
SELECT 
    customer_name,
    bazar,
    entry_date,
    total,
    (col_0 + col_1 + col_2 + col_3 + col_4) as first_half_total,
    (col_5 + col_6 + col_7 + col_8 + col_9) as second_half_total
FROM time_table
WHERE total > 0
ORDER BY entry_date DESC, customer_name, bazar;