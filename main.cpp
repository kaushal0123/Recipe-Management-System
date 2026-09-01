#include <iostream>
#include <string>
#include <fstream>
#include <sstream>
using namespace std;

class recipe {
public:
    string name;
    string ingredients[100];
    int calories;
    string category;
    recipe* next;
    int n1;

    recipe() {
        next = nullptr;
        n1 = 0;
        calories = 0;
    }
};

recipe* head = nullptr;
recipe* tail = nullptr;

void disp(recipe* current) {
    cout << "Ingredients : ";
    for (int i = 0; i < current->n1; i++) {
        cout << current->ingredients[i];
        if (i != current->n1 - 1) cout << ", ";
    }
    cout << "\nCategory : " << current->category << endl;
    cout << "Calories : " << current->calories << endl;
}

void add(recipe* temp) {
    if (head == nullptr) {
        head = tail = temp;
    } else {
        tail->next = temp;
        tail = temp;
    }
}

void display() {
    recipe* current = head;
    while (current != nullptr) {
        cout << "Recipe : " << current->name << " | Ingredients : ";
        for (int i = 0; i < current->n1; i++) {
            cout << current->ingredients[i];
            if (i != current->n1 - 1) cout << ", ";
        }
        cout << " | Calories : " << current->calories
             << " | Category : " << current->category << endl;
        current = current->next;
    }
}

void search(string s) {
    recipe* current = head;
    bool found = false;

    while (current != nullptr) {
        for (int i = 0; i < current->n1; i++) {
            if (current->ingredients[i] == s) {
                cout << "\nYou can make: " << current->name << endl;
                disp(current);
                found = true;
                break;
            }
        }
        current = current->next;
    }
    if (!found)
        cout << "\nNo recipe uses this ingredient.\n";
}

void dis(string s1) {
    recipe* current = head;
    bool found = false;

    while (current != nullptr) {
        if (current->name == s1) {
            found = true;
            disp(current);
            break;
        }
        current = current->next;
    }

    if (!found)
        cout << "The recipe is not in our database.\n";
}

void categ(string s) {
    recipe* current = head;
    bool found = false;

    while (current != nullptr) {
        if (current->category == s) {
            cout << "\nYou can make: " << current->name << endl;
            disp(current);
            found = true;
        }
        current = current->next;
    }

    if (!found)
        cout << "There is no recipe with this category.\n";
}

void meal_planner() {
    cout << "Enter breakfast, lunch & dinner recipe names:\n";
    string s1, s2, s3;
    cin >> s1 >> s2 >> s3;

    cout << "\nBreakfast:\n";
    dis(s1);
    cout << "\nLunch:\n";
    dis(s2);
    cout << "\nDinner:\n";
    dis(s3);
}

void meal_dec() {
    int low, high;
    string category;

    cout << "Enter calorie range (low high): ";
    cin >> low >> high;
    cout << "Enter category: ";
    cin >> category;

    recipe* current = head;
    bool found = false;
    while (current != nullptr) {
        if (current->calories >= low && current->calories <= high &&
            current->category == category) {
            cout << "\nYou can make: " << current->name << endl;
            disp(current);
            found = true;
        }
        current = current->next;
    }

    if (!found)
        cout << "No recipe found in this range & category.\n";
}

int main() {
    ifstream file("file.csv");
    string line;

    while (getline(file, line)) {
        if (line.empty()) continue;

        recipe* temp = new recipe;
        stringstream input(line);
        string tem;

        getline(input, temp->name, ',');

        getline(input, tem, ',');
        temp->n1 = stoi(tem);

        for (int i = 0; i < temp->n1; i++) {
            getline(input, temp->ingredients[i], ',');
        }

        getline(input, tem, ',');
        temp->calories = stoi(tem);

        getline(input, temp->category);

        add(temp);
    }
    file.close();

    int n;
    cout << "\nEnter 1 to add recipe\nEnter 2 to display all recipes\nEnter 3 to search by ingredient\nEnter 4 to search by category\nEnter 5 for recipe details\nEnter 6 smart meal suggestion\nEnter 7 full day meal plan\n0 to exit\n";
    cin >> n;

    while (n != 0) {
        if (n == 1) {
            recipe* temp = new recipe;
            cout << "Enter recipe name: ";
            cin >> temp->name;

            cout << "Enter number of ingredients: ";
            cin >> temp->n1;

            cout << "Enter each ingredient:\n";
            for (int i = 0; i < temp->n1; i++) {
                cin >> temp->ingredients[i];
            }

            cout << "Enter calories: ";
            cin >> temp->calories;

            cout << "Enter category: ";
            cin >> temp->category;

            ofstream out("file.csv", ios::app);
            out << "\n" << temp->name << "," << temp->n1 << ",";
            for (int i = 0; i < temp->n1; i++) out << temp->ingredients[i] << ",";
            out << temp->calories << "," << temp->category;
            out.close();

            add(temp);
        }

        else if (n == 2) display();
        else if (n == 3) {
            string s;
            cout << "Enter ingredient: ";
            cin >> s;
            search(s);
        }
        else if (n == 4) {
            string s;
            cout << "Enter category: ";
            cin >> s;
            categ(s);
        }
        else if (n == 5) {
            string s;
            cout << "Enter recipe name: ";
            cin >> s;
            dis(s);
        }
        else if (n == 6) {
            meal_dec();
        }
        else if (n == 7) {
            meal_planner();
        }
        else {
            cout << "Invalid choice\n";
        }

        cout << "\nEnter 1 to add recipe\nEnter 2 to display all recipes\nEnter 3 to search by ingredient\nEnter 4 to search by category\nEnter 5 for recipe details\nEnter 6 smart meal suggestion\nEnter 7 full day meal plan\n0 to exit\n";
        cin >> n;
    }

    return 0;
}
