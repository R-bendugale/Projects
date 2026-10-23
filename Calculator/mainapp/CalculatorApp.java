package mainapp;

import java.util.Scanner;
import operations.*;
import display.*;

public class CalculatorApp {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        System.out.print("Enter first number: ");
        int a = sc.nextInt();
        System.out.print("Enter second number: ");
        int b = sc.nextInt();

        Add add = new Add();
        Subtract sub = new Subtract();
        Multiply mul = new Multiply();
        Divide div = new Divide();
        printer printer = new printer();

        printer.show("Addition: " + add.add(a, b));
        printer.show("Subtraction: " + sub.subtract(a, b));
        printer.show("Multiplication: " + mul.multiply(a, b));
        printer.show("Division: " + div.divide(a, b));
    }
}
