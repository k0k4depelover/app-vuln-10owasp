CREATE DATABASE vuln_database_fix IF NOT EXISTS;

USE vuln_database_fix;

CREATE TABLE users IF NOT EXISTS(
  id INT PRIMARY KEY,
  username VARCHAR(50) NOT NULL,
  password VARCHAR(255) NOT NULL,
  role VARCHAR(15) NOT NULL
);

CREATE TABLE fines IF NOT EXISTS(
  id INT PRIMARY KEY,
  user_id INT,
  description VARCHAR(200),
  FOREIGN KEY(user_id) REFERENCES users(user_id),
  paid BOOLEAN DEFAULT FALSE
)


CREATE TABLE invoces(
  id INT PRIMARY KEY,
  fine_id INT,
  user_id INT,
  amount DECIMAL(10,2),
  stripe_charge_id INT,
  DATETIME created_at,
  FOREIGN KEY(fine_id) REFERENCES fines(fine_id),
  FOREIGN KEY(user_id) REFERENCES users(user_id)
)
