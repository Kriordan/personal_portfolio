Pod::Spec.new do |s|
  s.name = 'IntervalTimer'
  s.version = '1.0.0'
  s.summary = 'Offline interval workout audio and local workout storage'
  s.description = s.summary
  s.license = { :type => 'MIT' }
  s.author = 'Keith Riordan'
  s.homepage = 'https://github.com/Kriordan/personal_portfolio'
  s.source = { :git => 'https://github.com/Kriordan/personal_portfolio.git' }
  s.platform = :ios, '16.4'
  s.swift_version = '5.9'
  s.static_framework = true
  s.dependency 'ExpoModulesCore'
  s.frameworks = 'AVFoundation', 'CryptoKit'
  s.source_files = '*.{h,m,swift}'
  s.pod_target_xcconfig = { 'DEFINES_MODULE' => 'YES' }
end
