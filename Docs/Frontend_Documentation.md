# Frontend Documentation for Restaurant POS System

## Overview

This documentation covers the implementation details for three iOS/iPadOS applications:
1. POS App (iPad)
2. Customer Display App (iPad)
3. Admin Dashboard App (iPhone/iPad)

## Common Technical Requirements

- iOS/iPadOS 15.0+
- Swift 5.0+
- SwiftUI for UI components
- Combine framework for reactive programming
- URLSession for API communication
- WebSocket support for real-time updates

## Network Communication

### Backend Discovery

The POS system uses Zeroconf/Bonjour for automatic service discovery:

```swift
class BackendDiscovery: ObservableObject {
    @Published var serverURL: URL?
    private let serviceName = "Restaurant POS Server"
    private let serviceType = "_pos._tcp."
    private let domain = "local."
    
    func startDiscovery() {
        let browser = NetServiceBrowser()
        browser.delegate = self
        browser.searchForServices(ofType: serviceType, inDomain: domain)
    }
    
    func netServiceDidResolveAddress(_ sender: NetService) {
        guard let hostName = sender.hostName else { return }
        let port = sender.port
        serverURL = URL(string: "http://\(hostName):\(port)")
        
        if let data = sender.txtRecordData() {
            let dict = NetService.dictionary(fromTXTRecord: data)
            // Access properties:
            // - version
            // - api
            // - docs
        }
    }
}
```

### API Groups

#### System Administration
- Health monitoring
- Service management
- System logs
- USB device handling

```swift
struct SystemAPI {
    static func getHealth() async throws -> HealthStatus {
        let url = baseURL.appendingPathComponent("health")
        return try await APIClient.get(url)
    }
    
    static func getLogs() async throws -> [LogEntry] {
        let url = baseURL.appendingPathComponent("admin/logs")
        return try await APIClient.get(url)
    }
}
```

#### Authentication
- Staff login/logout
- PIN validation
- Session management

```swift
struct AuthAPI {
    static func login(pin: String) async throws -> AuthResponse {
        let url = baseURL.appendingPathComponent("auth/login")
        let body = ["pin": pin]
        return try await APIClient.post(url, body: body)
    }
}
```

#### Catalog Management
- Categories and items
- Modifiers and options
- Pricing

```swift
struct CatalogAPI {
    static func getCategories() async throws -> [Category] {
        let url = baseURL.appendingPathComponent("catalog/categories")
        return try await APIClient.get(url)
    }
    
    static func getItems(categoryId: Int) async throws -> [Item] {
        let url = baseURL.appendingPathComponent("catalog/items")
            .appendingQueryItem("category_id", value: categoryId)
        return try await APIClient.get(url)
    }
}
```

#### Order Management
- Order creation
- Status tracking
- History

```swift
struct OrderAPI {
    static func createOrder(items: [OrderItem]) async throws -> Order {
        let url = baseURL.appendingPathComponent("order")
        return try await APIClient.post(url, body: items)
    }
    
    static func getOrder(id: Int) async throws -> Order {
        let url = baseURL.appendingPathComponent("order/\(id)")
        return try await APIClient.get(url)
    }
}
```

#### Payment Processing
- Card payments
- Refunds
- Payment status

```swift
struct PaymentAPI {
    static func processCardPayment(orderId: Int, sourceId: String) async throws -> PaymentResult {
        let url = baseURL.appendingPathComponent("payment/card")
        let body = CardPayment(orderId: orderId, sourceId: sourceId)
        return try await APIClient.post(url, body: body)
    }
    
    static func refundPayment(orderId: Int, amount: Decimal) async throws -> RefundResult {
        let url = baseURL.appendingPathComponent("payment/refund")
        let body = RefundRequest(orderId: orderId, amount: amount)
        return try await APIClient.post(url, body: body)
    }
}
```

### WebSocket Integration

Real-time updates using WebSocket connection:

```swift
class WebSocketManager: ObservableObject {
    @Published var isConnected = false
    private var webSocket: URLSessionWebSocketTask?
    
    func connect(clientType: String, clientId: String) {
        guard let url = URL(string: "ws://\(host):\(port)/ws/\(clientType)/\(clientId)") else { return }
        
        let session = URLSession(configuration: .default)
        webSocket = session.webSocketTask(with: url)
        webSocket?.resume()
        
        receiveMessage()
    }
    
    private func receiveMessage() {
        webSocket?.receive { [weak self] result in
            switch result {
            case .success(let message):
                self?.handleMessage(message)
                self?.receiveMessage()
            case .failure(let error):
                self?.handleError(error)
            }
        }
    }
    
    private func handleMessage(_ message: URLSessionWebSocketTask.Message) {
        // Handle different message types:
        // - order_update
        // - payment_status
        // - system_status
    }
}
```

### Error Handling

Consistent error handling across all API calls:

```swift
enum APIError: Error {
    case networkError(Error)
    case invalidResponse
    case unauthorized
    case forbidden
    case notFound
    case validationError([String: String])
    case serverError(String)
}

extension APIError: LocalizedError {
    var errorDescription: String? {
        switch self {
        case .networkError(let error):
            return "Network error: \(error.localizedDescription)"
        case .unauthorized:
            return "Invalid credentials"
        case .forbidden:
            return "Access denied"
        case .notFound:
            return "Resource not found"
        case .validationError(let fields):
            return "Validation error: \(fields)"
        case .serverError(let message):
            return "Server error: \(message)"
        }
    }
}
```

### API Client

Generic API client for making requests:

```swift
struct APIClient {
    static func get<T: Decodable>(_ url: URL) async throws -> T {
        var request = URLRequest(url: url)
        request.addValue("application/json", forHTTPHeaderField: "Accept")
        
        let (data, response) = try await URLSession.shared.data(for: request)
        try validateResponse(response)
        return try JSONDecoder().decode(T.self, from: data)
    }
    
    static func post<T: Decodable, B: Encodable>(_ url: URL, body: B) async throws -> T {
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        try validateResponse(response)
        return try JSONDecoder().decode(T.self, from: data)
    }
}
```

## 1. POS App (iPad)

### Features
- Staff login with PIN
- Order management
- Payment processing
- Catalog browsing
- Real-time updates

### Architecture
```
POS/
├── App/
│   ├── POSApp.swift
│   └── AppDelegate.swift
├── Models/
│   ├── Order.swift
│   ├── Catalog.swift
│   ├── Staff.swift
│   └── Payment.swift
├── Views/
│   ├── Login/
│   │   ├── LoginView.swift
│   │   └── PINPadView.swift
│   ├── Orders/
│   │   ├── OrderView.swift
│   │   ├── CartView.swift
│   │   └── OrderHistoryView.swift
│   ├── Catalog/
│   │   ├── CatalogView.swift
│   │   ├── CategoryView.swift
│   │   └── ItemDetailView.swift
│   └── Payment/
│       ├── PaymentView.swift
│       └── SquareReaderView.swift
└── ViewModels/
    ├── OrderViewModel.swift
    ├── CatalogViewModel.swift
    └── PaymentViewModel.swift
```

### Key Components

#### Login Flow
```swift
struct LoginView: View {
    @StateObject private var viewModel = LoginViewModel()
    
    var body: some View {
        PINPadView(onSubmit: { pin in
            await viewModel.login(pin: pin)
        })
    }
}
```

#### Order Management
```swift
class OrderViewModel: ObservableObject {
    @Published var currentOrder: Order?
    @Published var orderItems: [OrderItem] = []
    
    func addItem(_ item: Item, quantity: Int = 1) {
        // Add item to order
    }
    
    func removeItem(_ item: OrderItem) {
        // Remove item from order
    }
    
    func applyDiscount(_ discount: Discount) {
        // Apply discount to order
    }
    
    func processPayment(_ method: PaymentMethod) async throws {
        // Handle payment processing
    }
}
```

#### Square Integration
```swift
class SquarePaymentHandler {
    func processCardPayment(amount: Decimal) async throws -> PaymentResult {
        // Initialize Square reader
        // Process payment
        // Handle result
    }
}
```

### UI/UX Guidelines

#### Layout
- Split view with catalog on left, cart on right
- Bottom bar for order history and settings
- Modal views for payment and modifiers

#### Color Scheme
```swift
extension Color {
    static let primaryBackground = Color("PrimaryBackground")
    static let secondaryBackground = Color("SecondaryBackground")
    static let accentColor = Color("AccentColor")
    static let textPrimary = Color("TextPrimary")
    static let textSecondary = Color("TextSecondary")
}
```

## 2. Customer Display App (iPad)

### Features
- Order display
- Payment status
- Promotional content
- Real-time updates

### Architecture
```
CustomerDisplay/
├── App/
│   └── CustomerDisplayApp.swift
├── Models/
│   └── DisplayOrder.swift
├── Views/
│   ├── OrderDisplayView.swift
│   ├── PaymentStatusView.swift
│   └── PromotionalView.swift
└── ViewModels/
    └── DisplayViewModel.swift
```

### Key Components

#### Order Display
```swift
struct OrderDisplayView: View {
    @StateObject private var viewModel = DisplayViewModel()
    
    var body: some View {
        VStack {
            // Order items
            // Subtotal, tax, total
            // Payment status
        }
        .onReceive(viewModel.orderUpdates) { order in
            // Update display
        }
    }
}
```

### UI/UX Guidelines
- Large, clear text for visibility
- High contrast colors
- Smooth transitions between states
- Clear payment instructions

## 3. Admin Dashboard App (iPhone/iPad)

### Features
- Staff management
- Sales reports
- Catalog management
- Square integration setup

### Architecture
```
AdminDashboard/
├── App/
│   └── AdminApp.swift
├── Models/
│   ├── Report.swift
│   └── Settings.swift
├── Views/
│   ├── Dashboard/
│   │   ├── DashboardView.swift
│   │   └── ReportView.swift
│   ├── Staff/
│   │   ├── StaffListView.swift
│   │   └── StaffDetailView.swift
│   └── Settings/
│       ├── SquareSettingsView.swift
│       └── PrinterSettingsView.swift
└── ViewModels/
    ├── ReportViewModel.swift
    └── StaffViewModel.swift
```

### Key Components

#### Staff Management
```swift
class StaffViewModel: ObservableObject {
    @Published var staff: [Staff] = []
    
    func createStaff(_ staff: Staff) async throws {
        // Create new staff member
    }
    
    func updateStaff(_ staff: Staff) async throws {
        // Update staff details
    }
}
```

#### Reports
```swift
class ReportViewModel: ObservableObject {
    func fetchDailyReport(date: Date) async throws -> Report {
        // Fetch daily sales report
    }
    
    func fetchRangeReport(start: Date, end: Date) async throws -> Report {
        // Fetch date range report
    }
}
```

### UI/UX Guidelines
- Tab-based navigation
- Data visualization for reports
- Form-based input for settings
- Confirmation dialogs for important actions

## API Integration

### Base API Client
```swift
class APIClient {
    static let shared = APIClient()
    
    func get<T: Decodable>(_ endpoint: Endpoint) async throws -> T {
        // Make GET request
    }
    
    func post<T: Decodable>(_ endpoint: Endpoint, body: Encodable) async throws -> T {
        // Make POST request
    }
}
```

### WebSocket Events
```swift
enum WebSocketEvent {
    case orderUpdate(Order)
    case paymentUpdate(Payment)
    case catalogUpdate(CatalogItem)
}

extension WebSocketManager {
    func handleEvent(_ event: WebSocketEvent) {
        // Process different event types
    }
}
```

## Error Handling

### Network Errors
```swift
enum APIError: Error {
    case networkError
    case serverError(String)
    case authenticationError
    case decodingError
}
```

### User Feedback
```swift
struct ErrorView: View {
    let error: Error
    let retryAction: () -> Void
    
    var body: some View {
        VStack {
            // Error message
            // Retry button
        }
    }
}
```

## Testing

### Unit Tests
```swift
class OrderViewModelTests: XCTestCase {
    func testAddItem() {
        // Test adding items to order
    }
    
    func testApplyDiscount() {
        // Test discount application
    }
}
```

### UI Tests
```swift
class POSUITests: XCTestCase {
    func testLoginFlow() {
        // Test login process
    }
    
    func testOrderCreation() {
        // Test creating new order
    }
}
```

## Deployment

### Requirements
- Apple Developer Account
- Xcode 13.0+
- Certificates and provisioning profiles

### Build Configuration
```swift
enum Environment {
    case development
    case staging
    case production
    
    var baseURL: URL {
        switch self {
        case .development: return URL(string: "http://localhost:8000")!
        case .staging: return URL(string: "http://staging.example.com")!
        case .production: return URL(string: "http://api.example.com")!
        }
    }
}
```

## Security

### Data Protection
- Keychain for sensitive data
- Secure enclave for PIN storage
- Network security with SSL pinning

### Access Control
- Role-based access control
- Biometric authentication for admin app
- Session management

## Performance

### Optimization
- Image caching
- Response caching
- Background tasks
- Memory management

### Monitoring
- Analytics integration
- Crash reporting
- Performance metrics

## Offline Support

### Data Persistence
```swift
class CacheManager {
    func saveToCache<T: Encodable>(_ object: T, key: String) {
        // Save to local storage
    }
    
    func loadFromCache<T: Decodable>(_ key: String) -> T? {
        // Load from local storage
    }
}
```

### Sync Strategy
- Background sync when online
- Conflict resolution
- Queue management for offline actions
