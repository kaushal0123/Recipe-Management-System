#include <iostream>
#include <string>
#include <fstream>
#include <sstream>
#include <vector>
#include <algorithm>
#include <cstdlib>
#include <ctime>
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

// ----------------------------------------------
//           BASIC EXISTING FUNCTIONS
// ----------------------------------------------

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

// ----------------------------------------------
//       🔥 NEW FEATURE 1: MULTI-INGREDIENT SEARCH
// ----------------------------------------------

void search_multi() {
    int count;
    cout << "Enter number of ingredients you have: ";
    cin >> count;

    vector<string> list(count);
    cout << "Enter ingredients:\n";
    for (int i = 0; i < count; i++) cin >> list[i];

    recipe* current = head;
    bool found = false;

    while (current != nullptr) {
        int match = 0;
        for (string ing : list) {
            for (int i = 0; i < current->n1; i++) {
                if (ing == current->ingredients[i]) match++;
            }
        }
        if (match == count) {
            cout << "\nYou can make: " << current->name << endl;
            disp(current);
            found = true;
        }
        current = current->next;
    }

    if (!found)
        cout << "\nNo recipe uses all these ingredients.\n";
}

// ----------------------------------------------
//        🔥 NEW FEATURE 2: SORT BY CALORIES
// ----------------------------------------------

void sort_by_calories() {
    vector<recipe*> arr;
    recipe* cur = head;

    while (cur != nullptr) {
        arr.push_back(cur);
        cur = cur->next;
    }

    sort(arr.begin(), arr.end(), [](recipe* a, recipe* b) {
        return a->calories < b->calories;
    });

    cout << "\nRecipes sorted by calories:\n";
    for (auto r : arr)
        cout << r->name << " - " << r->calories << " cal\n";
}

// ----------------------------------------------
// 🔥 NEW FEATURE 3: HEALTHY ALTERNATIVE
// ----------------------------------------------

void healthy_alternative(string dish) {
    recipe* target = head;

    while (target != nullptr && target->name != dish)
        target = target->next;

    if (!target) {
        cout << "Recipe not found.\n";
        return;
    }

    recipe* current = head;
    recipe* best = nullptr;

    while (current != nullptr) {
        if (current->category == target->category &&
            current->calories < target->calories) {
            if (!best || current->calories > best->calories)
                best = current;
        }
        current = current->next;
    }

    if (best) {
        cout << "\nHealthier alternative to " << dish << ":\n";
        disp(best);
    } else {
        cout << "\nNo healthier alternative available.\n";
    }
}

// ----------------------------------------------
//      🔥 NEW FEATURE 4: RANDOM SURPRISE
// ----------------------------------------------

void surprise_me() {
    srand(time(0));

    vector<recipe*> arr;
    recipe* cur = head;
    while (cur != nullptr) {
        arr.push_back(cur);
        cur = cur->next;
    }

    if (arr.size() == 0) {
        cout << "No recipes in database.\n";
        return;
    }

    int index = rand() % arr.size();
    cout << "\nSurprise Recipe Suggestion:\n";
    disp(arr[index]);
}

// ----------------------------------------------
//                 MAIN PROGRAM
// ----------------------------------------------

int main() {
    ifstream file("file.csv");
    string line;

    // Load from CSV
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

    cout << "\n=== Recipe Management System ===\n";
    cout << "1 Add recipe\n2 Display all recipes\n3 Search by ingredient\n4 Search by category\n5 Show recipe details\n6 Smart meal suggestion\n7 Full day meal plan\n8 Multi-ingredient search\n9 Sort recipes by calories\n10 Healthy alternative\n11 Surprise recipe\n0 Exit\n";

    cin >> n;

    while (n != 0) {
        if (n == 1) {
            recipe* temp = new recipe;
            cout << "Enter recipe name: ";
            cin >> temp->name;

            cout << "Enter number of ingredients: ";
            cin >> temp->n1;

            cout << "Enter each ingredient:\n";
            for (int i = 0; i < temp->n1; i++)
                cin >> temp->ingredients[i];

            cout << "Enter calories: ";
            cin >> temp->calories;

            cout << "Enter category: ";
            cin >> temp->category;

            // Save to file
            ofstream out("file.csv", ios::app);
            out << "\n" << temp->name << "," << temp->n1 << ",";
            for (int i = 0; i < temp->n1; i++)
                out << temp->ingredients[i] << ",";
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
        else if (n == 6) meal_dec();
        else if (n == 7) meal_planner();
        else if (n == 8) search_multi();
        else if (n == 9) sort_by_calories();
        else if (n == 10) {
            string d;
            cout << "Enter dish name: ";
            cin >> d;
            healthy_alternative(d);
        }
        else if (n == 11) surprise_me();
        else cout << "Invalid choice.\n";

        cout << "\n\n=== OPTIONS ===\n";
        cout << "1 Add recipe\n2 Display all recipes\n3 Search by ingredient\n4 Search by category\n5 Recipe details\n6 Meal suggestion\n7 Day meal plan\n8 Multi-ingredient search\n9 Sort by calories\n10 Healthy alternative\n11 Surprise me!\n0 Exit\n";
        cin >> n;
    }

    return 0;
}
