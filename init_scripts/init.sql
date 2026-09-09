CREATE DATABASE IF NOT EXISTS vuln_database_fix;

USE vuln_database_fix;

CREATE TABLE IF NOT EXISTS users (
  id INT PRIMARY KEY AUTO_INCREMENT,
  username VARCHAR(50) NOT NULL,
  password VARCHAR(255) NOT NULL,
  role VARCHAR(15) NOT NULL
);

CREATE TABLE IF NOT EXISTS fines (
  id INT PRIMARY KEY AUTO_INCREMENT,
  user_id INT,
  amount DECIMAL(10,2),
  description VARCHAR(200),
  paid BOOLEAN DEFAULT FALSE,
  FOREIGN KEY(user_id) REFERENCES users(id)
);


CREATE TABLE IF NOT EXISTS invoices(
  id INT PRIMARY KEY AUTO_INCREMENT,
  fine_id INT NOT NULL,
  user_id INT NOT NULL,
  amount DECIMAL(10,2),
  stripe_charge_id VARCHAR(255),
  stripe_status VARCHAR(100),
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(fine_id) REFERENCES fines(id),
  FOREIGN KEY(user_id) REFERENCES users(id)
);
