

--@block
CREATE TABLE Charge_Point(
    cpId INT PRIMARY KEY,
    model VARCHAR(20) NOT NULL,
    vendorName VARCHAR(50) NOT NULL,
    serialNumber VARCHAR(25),
    firmwareVersion VARCHAR(50)
);

CREATE TABLE EVSE(
    evseId INT PRIMARY KEY,
    cpId INT,
    FOREIGN KEY (cpId) REFERENCES Charge_Point(cpId)
);

CREATE TABLE Connector(
    id INT PRIMARY KEY,
    evseId INT,
    connectorStatus ENUM('Available', 'Occupied', 'Reserved', 'Unavailable', 'Faulted'),
    FOREIGN KEY (evseId) REFERENCES EVSE(evseId)
);