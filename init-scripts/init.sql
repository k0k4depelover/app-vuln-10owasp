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


USE vuln_database_fix;

-- 20 usuarios
INSERT INTO users (username, password, role) VALUES
('admin', '$2b$12$adminhash', 'admin'),
('juanperez', '$2b$12$userhash1', 'user'),
('mariagarcia', '$2b$12$userhash2', 'user'),
('carloslopez', '$2b$12$userhash3', 'user'),
('anarodriguez', '$2b$12$userhash4', 'user'),
('luismartinez', '$2b$12$userhash5', 'user'),
('sofiahernandez', '$2b$12$userhash6', 'user'),
('diegotorres', '$2b$12$userhash7', 'user'),
('elenaflores', '$2b$12$userhash8', 'user'),
('javiercastro', '$2b$12$userhash9', 'user'),
('lauraramirez', '$2b$12$userhash10', 'user'),
('pedrogomez', '$2b$12$userhash11', 'user'),
('valeriacruz', '$2b$12$userhash12', 'user'),
('andresmendoza', '$2b$12$userhash13', 'user'),
('gabrielasilva', '$2b$12$userhash14', 'user'),
('ricardovelasquez', '$2b$12$userhash15', 'user'),
('paulamorales', '$2b$12$userhash16', 'user'),
('fernandorojas', '$2b$12$userhash17', 'user'),
('danielaalvarez', '$2b$12$userhash18', 'user'),
('sergioortiz', '$2b$12$userhash19', 'user');

-- 12 multas
INSERT INTO fines (user_id, amount, description, paid) VALUES
(2, 150.00, 'Exceso de velocidad', FALSE),
(3, 75.50, 'Estacionamiento prohibido', FALSE),
(4, 300.00, 'Conducir sin licencia', FALSE),
(5, 125.00, 'Uso del telefono al conducir', FALSE),
(6, 90.00, 'No portar documentos', FALSE),
(7, 450.00, 'Conducir en estado de ebriedad', FALSE),
(8, 60.00, 'No respetar senal de alto', FALSE),
(9, 180.00, 'Exceso de velocidad en zona escolar', FALSE),
(10, 110.00, 'Circular sin luces', FALSE),
(11, 250.00, 'Cambio indebido de carril', FALSE),
(12, 80.00, 'No usar cinturon de seguridad', FALSE),
(13, 500.00, 'Reincidencia por exceso de velocidad', FALSE);
