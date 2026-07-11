package de.for3dsuite.growth;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Einstiegspunkt des Wachstumsdienstes (Baustein 5).
 *
 * Nimmt eine Baumliste + Bestandesmetadaten als JSON an, simuliert n Jahre mit
 * TreeGrOSS/BWINPro und gibt die Zukunftsbestaende zurueck. Die GPLv3-Komponente
 * (TreeGrOSS) bleibt in diesem eigenstaendigen Prozess isoliert; die uebrige
 * Suite kommuniziert nur ueber HTTP/JSON.
 */
@SpringBootApplication
public class GrowthServiceApplication {
    public static void main(String[] args) {
        SpringApplication.run(GrowthServiceApplication.class, args);
    }
}
