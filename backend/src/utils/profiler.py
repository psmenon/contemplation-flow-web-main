import time
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from tuneapi import tu

@dataclass
class OperationProfile:
    name: str
    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        self.start_time = time.time()
    
    def finish(self, **metadata):
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.metadata.update(metadata)
        return self

@dataclass
class RequestProfile:
    request_id: str
    operations: Dict[str, OperationProfile] = field(default_factory=dict)
    total_duration_ms: float = 0.0
    
    def add_operation(self, name: str) -> OperationProfile:
        profile = OperationProfile(name)
        self.operations[name] = profile
        return profile
    
    def finish(self):
        self.total_duration_ms = sum(op.duration_ms for op in self.operations.values())
        return self
    
    def print_summary(self):
        print(f"\n📊 Performance Profile for Request {self.request_id}")
        print(f"⏱️  Total Duration: {self.total_duration_ms:.2f}ms")
        print("\n📈 Operation Breakdown:")
        
        # Sort by duration
        sorted_ops = sorted(self.operations.values(), key=lambda x: x.duration_ms, reverse=True)
        
        for op in sorted_ops:
            percentage = (op.duration_ms / self.total_duration_ms * 100) if self.total_duration_ms > 0 else 0
            print(f"  • {op.name}: {op.duration_ms:.2f}ms ({percentage:.1f}%)")
            if op.metadata:
                for key, value in op.metadata.items():
                    print(f"    - {key}: {value}")
        
        print(f"\n🎯 Performance Insights:")
        if self.total_duration_ms > 5000:
            print("  ⚠️  SLOW: Total time > 5s")
        elif self.total_duration_ms > 2000:
            print("  ⚡ MODERATE: Total time 2-5s")
        else:
            print("  �� FAST: Total time < 2s")

# Global profiler instance
profiler = RequestProfile("default")

@asynccontextmanager
async def profile_operation(name: str, request_id: Optional[str] = None):
    """Context manager for profiling operations"""
    global profiler
    
    if request_id:
        profiler = RequestProfile(request_id)
    
    operation = profiler.add_operation(name)
    
    try:
        yield operation
    finally:
        operation.finish()

def get_profiler() -> RequestProfile:
    """Get the current profiler instance"""
    return profiler

def print_profiler_summary():
    """Print the current profiler summary"""
    profiler.finish()
    profiler.print_summary() 